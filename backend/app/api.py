from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import get_session
from app.geocoding import GeocoderUnavailable, geocoder
from app.models import (
    AuthSession,
    Friendship,
    Place,
    PlaceList,
    PlaceListItem,
    Recommendation,
    User,
)
from app.schemas import (
    AddPlaceIn,
    ClientConfigOut,
    GeocodeIn,
    GeocodeItemOut,
    GeocodeOut,
    LoginIn,
    PlaceListIn,
    PlaceListOut,
    PlaceOut,
    RecommendationIn,
    RecommendationOut,
    TokenOut,
    UserOut,
)
from app.security import new_token, verify_password

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


def visible_place_ids_subquery(user_id: int):
    """A place is visible if the user or one of their friends recommended it."""
    return select(Recommendation.place_id).where(
        or_(
            Recommendation.author_id == user_id,
            Recommendation.author_id.in_(friend_ids_subquery(user_id)),
        )
    )


def to_user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, display_name=user.display_name)


def to_place_out(place: Place) -> PlaceOut:
    return PlaceOut(id=place.id, name=place.name, address=place.address, lat=place.lat, lon=place.lon)


def to_recommendation_out(rec: Recommendation, viewer_id: int) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        text=rec.text,
        created_at=rec.created_at,
        author=to_user_out(rec.author),
        place=to_place_out(rec.place),
        is_own=rec.author_id == viewer_id,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config")
def client_config() -> ClientConfigOut:
    return ClientConfigOut(tile_url=settings.tile_url, tile_attribution=settings.tile_attribution)


@router.post("/auth/login")
def login(body: LoginIn, session: DbSession) -> TokenOut:
    user = session.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")
    token = new_token()
    session.add(AuthSession(token=token, user_id=user.id))
    session.commit()
    return TokenOut(token=token)


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return to_user_out(user)


@router.get("/friends")
def friends(user: CurrentUser, session: DbSession) -> list[UserOut]:
    rows = session.scalars(
        select(User).where(User.id.in_(friend_ids_subquery(user.id))).order_by(User.display_name)
    )
    return [to_user_out(u) for u in rows]


@router.get("/feed")
def feed(
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[RecommendationOut]:
    rows = session.scalars(
        select(Recommendation)
        .options(joinedload(Recommendation.author), joinedload(Recommendation.place))
        .where(
            or_(
                Recommendation.author_id == user.id,
                Recommendation.author_id.in_(friend_ids_subquery(user.id)),
            )
        )
        .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        .limit(limit)
    )
    return [to_recommendation_out(r, user.id) for r in rows]


@router.post("/recommendations", status_code=status.HTTP_201_CREATED)
def create_recommendation(body: RecommendationIn, user: CurrentUser, session: DbSession) -> RecommendationOut:
    place = Place(name=body.name, address=body.address, lat=body.lat, lon=body.lon, created_by=user.id)
    session.add(place)
    session.flush()
    rec = Recommendation(author_id=user.id, place_id=place.id, text=body.text)
    session.add(rec)
    session.commit()
    session.refresh(rec, ["author", "place"])
    return to_recommendation_out(rec, user.id)


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
        results=[GeocodeItemOut(display_name=r.display_name, lat=r.lat, lon=r.lon) for r in results],
        cached=cached,
    )


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


@router.delete("/lists/{list_id}/places/{place_id}")
def remove_place_from_list(list_id: int, place_id: int, user: CurrentUser, session: DbSession) -> PlaceListOut:
    place_list = owned_list(session, list_id, user)
    item = session.get(PlaceListItem, (place_list.id, place_id))
    if item is not None:
        session.delete(item)
        session.commit()
    return load_list_out(session, place_list)
