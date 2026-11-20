import csv
import io
import secrets
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import get_session
from app.geocoding import GeocoderUnavailable, geocoder
from app.images import MAX_BYTES, ImageRejected, inspect_image
from app.models import (
    AuthSession,
    CloseFriend,
    FriendRequest,
    Friendship,
    PerfSample,
    Place,
    PlaceList,
    PlaceListItem,
    Recommendation,
    RecommendationAudience,
    RecommendationLike,
    RecommendationPhoto,
    RecommendationView,
    User,
)
from app.schemas import (
    AddPlaceIn,
    ClientConfigOut,
    CloseFriendIn,
    FriendOut,
    GeocodeIn,
    GeocodeItemOut,
    FriendRequestIn,
    FriendRequestOut,
    GeocodeOut,
    LoginIn,
    MeOut,
    PasswordChangeIn,
    PerfSampleIn,
    ProfileOut,
    ProfileUpdate,
    RegisterIn,
    PlaceListIn,
    PlaceListOut,
    PhotoOut,
    PlaceOut,
    RecommendationIn,
    RecommendationOut,
    ReverseIn,
    ReverseOut,
    TokenOut,
    UserOut,
    UserSearchOut,
)
from app.security import LOGIN_PATTERN, hash_password, new_token, verify_password

router = APIRouter(prefix="/api")

DbSession = Annotated[Session, Depends(get_session)]


def current_user(session: DbSession, authorization: Annotated[str | None, Header()] = None) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нужен вход")
    auth = session.get(AuthSession, authorization.removeprefix("Bearer "))
    if auth is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия не найдена")
    user = session.get(User, auth.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def friend_ids_subquery(user_id: int):
    return select(Friendship.friend_id).where(Friendship.user_id == user_id)


def recommendation_visible_to(viewer_id: int):
    """Author always sees the recommendation. Everyone else must be a friend inside the rule."""
    in_audience = exists(
        select(RecommendationAudience.user_id).where(
            RecommendationAudience.recommendation_id == Recommendation.id,
            RecommendationAudience.user_id == viewer_id,
        )
    )
    is_close = exists(
        select(CloseFriend.friend_id).where(
            CloseFriend.user_id == Recommendation.author_id,
            CloseFriend.friend_id == viewer_id,
        )
    )
    friend_rule = or_(
        Recommendation.visibility == "friends",
        and_(Recommendation.visibility == "close", is_close),
        and_(Recommendation.visibility == "allow", in_audience),
        and_(Recommendation.visibility == "deny", ~in_audience),
    )
    released = and_(
        Recommendation.status == "published",
        or_(Recommendation.publish_at.is_(None), Recommendation.publish_at <= func.now()),
    )
    return or_(
        Recommendation.author_id == viewer_id,
        and_(Recommendation.author_id.in_(friend_ids_subquery(viewer_id)), friend_rule, released),
    )


def visible_place_ids_subquery(user_id: int):
    """A place is visible only through a recommendation the user is allowed to see."""
    return select(Recommendation.place_id).where(recommendation_visible_to(user_id))


def to_user_out(user: User) -> UserOut:
    return UserOut(id=user.id, public_id=user.public_id, username=user.username, display_name=user.display_name)


def to_me(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        public_id=user.public_id,
        login=user.login,
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        profile_visibility=user.profile_visibility,
        theme=user.theme,
        has_avatar=user.avatar_path is not None,
    )


def profile_visible(session: Session, viewer: User, owner: User) -> bool:
    if viewer.id == owner.id or owner.profile_visibility == "everyone":
        return True
    if owner.profile_visibility == "friends":
        return session.get(Friendship, (viewer.id, owner.id)) is not None
    return False


def to_profile(owner: User, visible: bool) -> ProfileOut:
    return ProfileOut(
        public_id=owner.public_id,
        username=owner.username,
        display_name=owner.display_name,
        bio=owner.bio if visible else "",
        has_avatar=visible and owner.avatar_path is not None,
    )


def avatar_dir() -> Path:
    path = Path(settings.upload_dir) / "avatars"
    path.mkdir(parents=True, exist_ok=True)
    return path


def avatar_file(name: str) -> Path:
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фото нет")
    directory = avatar_dir().resolve()
    path = (directory / name).resolve()
    if path.parent != directory or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фото нет")
    return path


def avatar_media_type(path: Path) -> str:
    if path.suffix == ".png":
        return "image/png"
    if path.suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


def to_place_out(place: Place) -> PlaceOut:
    return PlaceOut(
        id=place.id, name=place.name, address=place.address, lat=place.lat, lon=place.lon, city=place.city
    )


def like_state(session: Session, viewer_id: int, recommendation_ids: list[int]) -> tuple[set[int], dict[int, int]]:
    if not recommendation_ids:
        return set(), {}
    liked = set(
        session.scalars(
            select(RecommendationLike.recommendation_id).where(
                RecommendationLike.user_id == viewer_id,
                RecommendationLike.recommendation_id.in_(recommendation_ids),
            )
        )
    )
    counts = dict(
        session.execute(
            select(RecommendationLike.recommendation_id, func.count())
            .where(RecommendationLike.recommendation_id.in_(recommendation_ids))
            .group_by(RecommendationLike.recommendation_id)
        ).all()
    )
    return liked, {key: int(value) for key, value in counts.items()}


def photos_by_recommendation(session: Session, recommendation_ids: list[int]) -> dict[int, list[PhotoOut]]:
    grouped: dict[int, list[PhotoOut]] = {recommendation_id: [] for recommendation_id in recommendation_ids}
    if not recommendation_ids:
        return grouped
    rows = session.scalars(
        select(RecommendationPhoto)
        .where(RecommendationPhoto.recommendation_id.in_(recommendation_ids))
        .order_by(RecommendationPhoto.position, RecommendationPhoto.id)
    )
    for row in rows:
        grouped.setdefault(row.recommendation_id, []).append(PhotoOut(id=row.id))
    return grouped


def to_recommendation_out(
    rec: Recommendation, viewer_id: int, liked: bool, like_count: int, photos: list[PhotoOut]
) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        text=rec.text,
        created_at=rec.created_at,
        author=to_user_out(rec.author),
        place=to_place_out(rec.place),
        is_own=rec.author_id == viewer_id,
        visibility=rec.visibility,
        liked=liked,
        like_count=like_count,
        status=rec.status,
        photos=photos,
    )


def recommendation_outs(session: Session, viewer_id: int, rows: list[Recommendation]) -> list[RecommendationOut]:
    ids = [row.id for row in rows]
    liked, counts = like_state(session, viewer_id, ids)
    photos = photos_by_recommendation(session, ids)
    return [
        to_recommendation_out(row, viewer_id, row.id in liked, counts.get(row.id, 0), photos.get(row.id, []))
        for row in rows
    ]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config")
def client_config() -> ClientConfigOut:
    return ClientConfigOut(tile_url=settings.tile_url, tile_attribution=settings.tile_attribution)


def issue_token(session: Session, user: User) -> TokenOut:
    token = new_token()
    session.add(AuthSession(token=token, user_id=user.id))
    session.commit()
    return TokenOut(token=token)


def new_username(session: Session) -> str:
    for _ in range(20):
        candidate = f"user{secrets.randbelow(100_000_000):08d}"
        taken = session.scalar(select(User.id).where(User.username == candidate))
        if taken is None:
            return candidate
    raise HTTPException(status.HTTP_409_CONFLICT, "Не удалось подобрать username")


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, session: DbSession) -> TokenOut:
    if session.scalar(select(User.id).where(User.login == body.login)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Такой логин уже занят")
    username = body.username if body.username is not None else new_username(session)
    if session.scalar(select(User.id).where(User.username == username)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Такой username уже занят")
    user = User(
        login=body.login,
        username=username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Такой логин или username уже занят") from None
    return issue_token(session, user)


@router.post("/auth/login")
def login(body: LoginIn, session: DbSession) -> TokenOut:
    user = session.scalar(select(User).where(User.login == body.login))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")
    return issue_token(session, user)


@router.get("/me")
def me(user: CurrentUser) -> MeOut:
    return to_me(user)


@router.patch("/me")
def update_me(body: ProfileUpdate, user: CurrentUser, session: DbSession) -> MeOut:
    changes = body.model_dump(exclude_unset=True)
    if "username" in changes and changes["username"] != user.username:
        taken = session.scalar(select(User.id).where(User.username == changes["username"]))
        if taken is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Такой username уже занят")
    for field, value in changes.items():
        setattr(user, field, value)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Такой username уже занят") from None
    session.refresh(user)
    return to_me(user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChangeIn, user: CurrentUser, session: DbSession) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный текущий пароль")
    user.password_hash = hash_password(body.password)
    session.commit()


@router.post("/me/avatar")
async def upload_avatar(
    user: CurrentUser,
    session: DbSession,
    file: Annotated[UploadFile, File()],
) -> MeOut:
    data = await file.read(MAX_BYTES + 1)
    await file.close()
    try:
        extension = inspect_image(data)
    except ImageRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    name = f"{secrets.token_hex(16)}.{extension}"
    (avatar_dir() / name).write_bytes(data)
    previous = user.avatar_path
    user.avatar_path = name
    session.commit()
    if previous:
        (avatar_dir() / previous).unlink(missing_ok=True)
    return to_me(user)


@router.get("/me/avatar")
def my_avatar(user: CurrentUser) -> FileResponse:
    if not user.avatar_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фото нет")
    path = avatar_file(user.avatar_path)
    return FileResponse(path, media_type=avatar_media_type(path))


def relation_of(session: Session, viewer: User, other: User) -> str:
    if session.get(Friendship, (viewer.id, other.id)) is not None:
        return "friend"
    outgoing = session.scalar(
        select(FriendRequest.id).where(
            FriendRequest.from_user_id == viewer.id,
            FriendRequest.to_user_id == other.id,
            FriendRequest.status == "pending",
        )
    )
    if outgoing is not None:
        return "outgoing"
    incoming = session.scalar(
        select(FriendRequest.id).where(
            FriendRequest.from_user_id == other.id,
            FriendRequest.to_user_id == viewer.id,
            FriendRequest.status == "pending",
        )
    )
    if incoming is not None:
        return "incoming"
    return "none"


@router.get("/users/search")
def search_users(
    user: CurrentUser,
    session: DbSession,
    q: Annotated[str, Query(min_length=1, max_length=50)],
) -> list[UserSearchOut]:
    term = q.strip()
    if not term or any(ord(char) < 32 or char in "<>" for char in term):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Некорректный запрос")
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    close_ids = set(session.scalars(select(CloseFriend.friend_id).where(CloseFriend.user_id == user.id)))
    rows = session.scalars(
        select(User)
        .where(User.id != user.id, User.username.ilike(f"%{escaped}%", escape="\\"))
        .order_by(User.username)
        .limit(20)
    )
    return [
        UserSearchOut(
            public_id=row.public_id,
            username=row.username,
            display_name=row.display_name,
            relation=relation_of(session, user, row),
            is_close=row.id in close_ids,
        )
        for row in rows
    ]


def pending_between(session: Session, left_id: int, right_id: int) -> FriendRequest | None:
    return session.scalar(
        select(FriendRequest).where(
            FriendRequest.status == "pending",
            or_(
                and_(FriendRequest.from_user_id == left_id, FriendRequest.to_user_id == right_id),
                and_(FriendRequest.from_user_id == right_id, FriendRequest.to_user_id == left_id),
            ),
        )
    )


@router.post("/friend-requests", status_code=status.HTTP_201_CREATED)
def create_friend_request(body: FriendRequestIn, user: CurrentUser, session: DbSession) -> FriendRequestOut:
    target = session.scalar(select(User).where(User.username == body.username))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    if target.id == user.id or session.get(Friendship, (user.id, target.id)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Заявка не нужна")
    if pending_between(session, user.id, target.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Заявка уже отправлена")
    row = FriendRequest(from_user_id=user.id, to_user_id=target.id, status="pending")
    session.add(row)
    session.commit()
    session.refresh(row)
    return FriendRequestOut(
        id=row.id, public_id=target.public_id, username=target.username, display_name=target.display_name
    )


@router.get("/friend-requests")
def incoming_friend_requests(user: CurrentUser, session: DbSession) -> list[FriendRequestOut]:
    rows = session.scalars(
        select(FriendRequest)
        .options(joinedload(FriendRequest.from_user))
        .where(FriendRequest.to_user_id == user.id, FriendRequest.status == "pending")
        .order_by(FriendRequest.id)
    )
    return [
        FriendRequestOut(
            id=row.id,
            public_id=row.from_user.public_id,
            username=row.from_user.username,
            display_name=row.from_user.display_name,
        )
        for row in rows
    ]


def own_pending_request(session: Session, request_id: int, user: User) -> FriendRequest:
    row = session.get(FriendRequest, request_id)
    if row is None or row.status != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    if row.to_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Эту заявку может решить только получатель")
    return row


@router.post("/friend-requests/{request_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
def accept_friend_request(request_id: int, user: CurrentUser, session: DbSession) -> Response:
    row = own_pending_request(session, request_id, user)
    row.status = "accepted"
    session.add(Friendship(user_id=row.from_user_id, friend_id=row.to_user_id))
    session.add(Friendship(user_id=row.to_user_id, friend_id=row.from_user_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/friend-requests/{request_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_friend_request(request_id: int, user: CurrentUser, session: DbSession) -> Response:
    row = own_pending_request(session, request_id, user)
    row.status = "rejected"
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{public_id}")
def user_profile(public_id: uuid.UUID, viewer: CurrentUser, session: DbSession) -> ProfileOut:
    owner = session.scalar(select(User).where(User.public_id == public_id))
    if owner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    return to_profile(owner, profile_visible(session, viewer, owner))


@router.get("/users/{public_id}/avatar")
def user_avatar(public_id: uuid.UUID, viewer: CurrentUser, session: DbSession) -> FileResponse:
    owner = session.scalar(select(User).where(User.public_id == public_id))
    if owner is None or not owner.avatar_path or not profile_visible(session, viewer, owner):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фото нет")
    path = avatar_file(owner.avatar_path)
    return FileResponse(path, media_type=avatar_media_type(path))


def friend_user(session: Session, user: User, username: str) -> User:
    if not LOGIN_PATTERN.fullmatch(username):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Друг не найден")
    friend = session.scalar(select(User).where(User.username == username))
    if friend is None or session.get(Friendship, (user.id, friend.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Друг не найден")
    return friend


@router.get("/friends")
def friends(user: CurrentUser, session: DbSession) -> list[FriendOut]:
    close_ids = set(session.scalars(select(CloseFriend.friend_id).where(CloseFriend.user_id == user.id)))
    rows = session.scalars(
        select(User).where(User.id.in_(friend_ids_subquery(user.id))).order_by(User.display_name)
    )
    return [
        FriendOut(id=row.id, username=row.username, display_name=row.display_name, is_close=row.id in close_ids)
        for row in rows
    ]


@router.put("/friends/{username}/close", status_code=status.HTTP_204_NO_CONTENT)
def set_close_friend(username: str, body: CloseFriendIn, user: CurrentUser, session: DbSession) -> Response:
    friend = friend_user(session, user, username)
    mark = session.get(CloseFriend, (user.id, friend.id))
    if body.close and mark is None:
        session.add(CloseFriend(user_id=user.id, friend_id=friend.id))
    if not body.close and mark is not None:
        session.delete(mark)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/feed")
def feed(
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    unseen: bool = False,
    city: Annotated[str, Query(max_length=120)] = "",
    author: Annotated[str, Query(max_length=80)] = "",
) -> list[RecommendationOut]:
    city = " ".join(city.split())
    author = author.strip()
    if any(ord(ch) < 32 or ch in "<>" for ch in city):
        return []
    if author and not LOGIN_PATTERN.fullmatch(author):
        return []
    filters = [recommendation_visible_to(user.id)]
    if unseen:
        already_seen = exists(
            select(RecommendationView.recommendation_id).where(
                RecommendationView.user_id == user.id,
                RecommendationView.recommendation_id == Recommendation.id,
            )
        )
        filters.append(Recommendation.author_id != user.id)
        filters.append(~already_seen)
    if city:
        filters.append(Recommendation.place.has(Place.city == city))
    if author:
        filters.append(Recommendation.author.has(User.username == author))
    rows = session.scalars(
        select(Recommendation)
        .options(joinedload(Recommendation.author), joinedload(Recommendation.place))
        .where(*filters)
        .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        .limit(limit)
    )
    return recommendation_outs(session, user.id, list(rows))


def remember_view(session: Session, user_id: int, recommendation_id: int) -> None:
    if session.get(RecommendationView, (user_id, recommendation_id)) is None:
        session.add(RecommendationView(user_id=user_id, recommendation_id=recommendation_id))
        session.commit()


@router.get("/recommendations/{recommendation_id}")
def recommendation_page(recommendation_id: int, user: CurrentUser, session: DbSession) -> RecommendationOut:
    row = session.scalar(
        select(Recommendation)
        .options(joinedload(Recommendation.author), joinedload(Recommendation.place))
        .where(Recommendation.id == recommendation_id, recommendation_visible_to(user.id))
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Рекомендация не найдена")
    remember_view(session, user.id, row.id)
    return recommendation_outs(session, user.id, [row])[0]


@router.post("/recommendations/{recommendation_id}/like")
def toggle_like(recommendation_id: int, user: CurrentUser, session: DbSession) -> RecommendationOut:
    row = session.scalar(
        select(Recommendation)
        .options(joinedload(Recommendation.author), joinedload(Recommendation.place))
        .where(Recommendation.id == recommendation_id, recommendation_visible_to(user.id))
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Рекомендация не найдена")
    existing = session.get(RecommendationLike, (user.id, row.id))
    if existing is None:
        session.add(RecommendationLike(user_id=user.id, recommendation_id=row.id))
    else:
        session.delete(existing)
    session.commit()
    return recommendation_outs(session, user.id, [row])[0]


PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_RECOMMENDATION_PHOTOS = 5


def photo_dir() -> Path:
    path = Path(settings.upload_dir) / "recommendations"
    path.mkdir(parents=True, exist_ok=True)
    return path


def stored_photo(name: str) -> Path:
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фото нет")
    directory = photo_dir().resolve()
    path = (directory / name).resolve()
    if path.parent != directory or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фото нет")
    return path


def visible_recommendation(session: Session, recommendation_id: int, user: User) -> Recommendation:
    row = session.scalar(
        select(Recommendation)
        .options(joinedload(Recommendation.author), joinedload(Recommendation.place))
        .where(Recommendation.id == recommendation_id, recommendation_visible_to(user.id))
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Рекомендация не найдена")
    return row


@router.post("/recommendations/{recommendation_id}/photos")
async def add_recommendation_photo(
    recommendation_id: int,
    user: CurrentUser,
    session: DbSession,
    file: Annotated[UploadFile, File()],
) -> RecommendationOut:
    row = visible_recommendation(session, recommendation_id, user)
    if row.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Фото добавляет автор")
    count = session.scalar(
        select(func.count())
        .select_from(RecommendationPhoto)
        .where(RecommendationPhoto.recommendation_id == row.id)
    )
    if count >= MAX_RECOMMENDATION_PHOTOS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Можно приложить не больше 5 фотографий")
    if Path(file.filename or "").suffix.lower() not in PHOTO_SUFFIXES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Нужна фотография JPEG, PNG или WebP")
    data = await file.read(MAX_BYTES + 1)
    await file.close()
    try:
        extension = inspect_image(data)
    except ImageRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    name = f"{secrets.token_hex(16)}.{extension}"
    (photo_dir() / name).write_bytes(data)
    session.add(RecommendationPhoto(recommendation_id=row.id, stored_name=name, position=int(count)))
    session.commit()
    return recommendation_outs(session, user.id, [row])[0]


@router.get("/recommendations/{recommendation_id}/photos/{photo_id}")
def recommendation_photo(
    recommendation_id: int, photo_id: int, user: CurrentUser, session: DbSession
) -> FileResponse:
    visible_recommendation(session, recommendation_id, user)
    photo = session.get(RecommendationPhoto, photo_id)
    if photo is None or photo.recommendation_id != recommendation_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фото нет")
    path = stored_photo(photo.stored_name)
    return FileResponse(path, media_type=avatar_media_type(path))


def audience_friends(session: Session, user: User, usernames: list[str]) -> list[User]:
    found: list[User] = []
    seen: set[int] = set()
    for username in usernames:
        friend = session.scalar(select(User).where(User.username == username))
        if friend is None or friend.id == user.id or session.get(Friendship, (user.id, friend.id)) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "В список можно добавить только друзей")
        if friend.id not in seen:
            found.append(friend)
            seen.add(friend.id)
    return found


@router.post("/recommendations", status_code=status.HTTP_201_CREATED)
def create_recommendation(body: RecommendationIn, user: CurrentUser, session: DbSession) -> RecommendationOut:
    if body.visibility in {"friends", "close"} and body.audience:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Список нужен только для выбранных пользователей")
    if body.draft and body.publish_at is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "У черновика нет времени публикации")
    place_list = owned_list(session, body.list_id, user) if body.list_id is not None else None
    selected = audience_friends(session, user, body.audience) if body.visibility in {"allow", "deny"} else []
    place = Place(
        name=body.name,
        address=body.address,
        lat=body.lat,
        lon=body.lon,
        created_by=user.id,
        point_corrected=body.point_corrected,
        city=body.city,
    )
    session.add(place)
    session.flush()
    rec = Recommendation(
        author_id=user.id,
        place_id=place.id,
        text=body.text,
        visibility=body.visibility,
        status="draft" if body.draft else "published",
        publish_at=None if body.draft else body.publish_at,
    )
    session.add(rec)
    session.flush()
    for friend in selected:
        session.add(RecommendationAudience(recommendation_id=rec.id, user_id=friend.id))
    if place_list is not None and session.get(PlaceListItem, (place_list.id, place.id)) is None:
        session.add(PlaceListItem(list_id=place_list.id, place_id=place.id))
    session.commit()
    session.refresh(rec, ["author", "place"])
    return recommendation_outs(session, user.id, [rec])[0]


@router.post("/geocode")
def geocode(body: GeocodeIn, user: CurrentUser, session: DbSession) -> GeocodeOut:
    try:
        results, cached = geocoder.search(session, body.query)
    except GeocoderUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Поиск адреса недоступен, отметьте место на карте вручную",
        ) from exc
    return GeocodeOut(
        results=[
            GeocodeItemOut(display_name=r.display_name, lat=r.lat, lon=r.lon, city=r.city) for r in results
        ],
        cached=cached,
    )


@router.post("/geocode/reverse")
def reverse_geocode(body: ReverseIn, user: CurrentUser, session: DbSession) -> ReverseOut:
    try:
        address, city, cached = geocoder.reverse(session, body.lat, body.lon)
    except GeocoderUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Адрес точки недоступен, место можно сохранить без адреса",
        ) from exc
    return ReverseOut(address=address, city=city, cached=cached)


def load_list_out(session: Session, place_list: PlaceList) -> PlaceListOut:
    items = session.scalars(
        select(PlaceListItem)
        .options(joinedload(PlaceListItem.place))
        .where(PlaceListItem.list_id == place_list.id)
        .order_by(PlaceListItem.added_at.desc())
    )
    return PlaceListOut(id=place_list.id, title=place_list.title, places=[to_place_out(i.place) for i in items])


def owned_list(session: Session, list_id: int, user: User) -> PlaceList:
    place_list = session.get(PlaceList, list_id)
    if place_list is None or place_list.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Список не найден")
    return place_list


@router.get("/lists")
def lists(user: CurrentUser, session: DbSession) -> list[PlaceListOut]:
    rows = session.scalars(select(PlaceList).where(PlaceList.owner_id == user.id).order_by(PlaceList.id))
    return [load_list_out(session, pl) for pl in rows]


@router.post("/lists", status_code=status.HTTP_201_CREATED)
def create_list(body: PlaceListIn, user: CurrentUser, session: DbSession) -> PlaceListOut:
    existing = session.scalar(
        select(PlaceList).where(PlaceList.owner_id == user.id, PlaceList.title == body.title)
    )
    if existing is not None:
        return load_list_out(session, existing)
    place_list = PlaceList(owner_id=user.id, title=body.title)
    session.add(place_list)
    session.commit()
    return load_list_out(session, place_list)


@router.post("/lists/{list_id}/places")
def add_place_to_list(list_id: int, body: AddPlaceIn, user: CurrentUser, session: DbSession) -> PlaceListOut:
    place_list = owned_list(session, list_id, user)
    visible = session.scalar(
        select(Place.id).where(Place.id == body.place_id, Place.id.in_(visible_place_ids_subquery(user.id)))
    )
    if visible is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Место не найдено")
    if session.get(PlaceListItem, (place_list.id, body.place_id)) is None:
        session.add(PlaceListItem(list_id=place_list.id, place_id=body.place_id))
        session.commit()
    return load_list_out(session, place_list)


@router.post("/perf", status_code=status.HTTP_204_NO_CONTENT)
def save_perf_sample(
    body: PerfSampleIn,
    user: CurrentUser,
    session: DbSession,
    user_agent: Annotated[str, Header()] = "",
) -> None:
    session.add(PerfSample(**body.model_dump(), user_agent=user_agent[:400]))
    session.commit()


PERF_COLUMNS = [
    "series",
    "seq",
    "total_ms",
    "dom_ready_ms",
    "feed_ms",
    "server_ms",
    "markers",
    "navigation_type",
    "user_agent",
    "created_at",
]


@router.get("/perf.csv")
def export_perf_samples(session: DbSession) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(PERF_COLUMNS)
    for sample in session.scalars(select(PerfSample).order_by(PerfSample.id)):
        writer.writerow([getattr(sample, column) for column in PERF_COLUMNS])
    return Response(buffer.getvalue(), media_type="text/csv; charset=utf-8")


@router.delete("/lists/{list_id}/places/{place_id}")
def remove_place_from_list(list_id: int, place_id: int, user: CurrentUser, session: DbSession) -> PlaceListOut:
    place_list = owned_list(session, list_id, user)
    item = session.get(PlaceListItem, (place_list.id, place_id))
    if item is not None:
        session.delete(item)
        session.commit()
    return load_list_out(session, place_list)
