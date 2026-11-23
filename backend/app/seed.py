"""Brings the schema to the latest migration, clears user data and loads the demo.

Places are real Moscow venues. Each recommendation stores a photograph of that venue.
Credits are in app/seed_photos/SOURCES.txt. Logins of the demo accounts stay stable
because the tests and the trial script sign in with them.
"""

import random
import secrets
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.migrations import upgrade_to_head
from app.models import (
    Friendship,
    GeocodeCacheEntry,
    PerfSample,
    Place,
    PlaceList,
    Recommendation,
    RecommendationPhoto,
    User,
)
from app.security import hash_password

DEMO_PASSWORD = "demo1234"
# login, display name, surname, bio
MAIN_USER = ("lesha", "Лёша", "Волков", "Собираю места, куда можно пойти после пар.")
FRIENDS = [
    ("anya", "Аня", "Соколова", "Люблю тихие залы и кофе рядом."),
    ("sasha", "Саша", "Орлов", "Чаще зову гулять, чем сидеть дома."),
    ("kristina", "Кристина", "Белова", "Ищу места, где можно долго разговаривать."),
    ("dima", "Дима", "Кузнецов", "Хожу на выставки и в библиотеки."),
    ("masha", "Маша", "Лебедева", "Собираю дворы и парки в центре."),
]
STRANGERS = [
    ("stranger1", "Никита", "Егоров", "Друг Ани, с Лёшей не знаком."),
    ("stranger2", "Оля", "Смирнова", "Ходит по тем же местам, но в другой компании."),
    ("stranger3", "Паша", "Новиков", "Редко бывает в центре, зато советует точно."),
]
RECOMMENDATIONS_PER_FRIEND = 10
RECOMMENDATIONS_PER_STRANGER = 10
PHOTO_ROOT = Path(__file__).resolve().parent / "seed_photos"
AVATAR_ROOT = PHOTO_ROOT / "avatars"
VENUES = [
    {
        "name": "Парк Горького",
        "address": "Москва, ул. Крымский Вал, 9",
        "lat": 55.7308,
        "lon": 37.6027,
        "category": "walk",
        "photo": "gorky.jpg",
        "text": "Вечером хорошо идти вдоль набережной и сесть у фонтана.",
    },
    {
        "name": "Нескучный сад",
        "address": "Москва, Ленинский проспект, 30",
        "lat": 55.7183,
        "lon": 37.5890,
        "category": "walk",
        "photo": "neskuchny.jpg",
        "text": "Тихие аллеи, удобно гулять, когда в Парке Горького уже шумно.",
    },
    {
        "name": "Патриаршие пруды",
        "address": "Москва, Малая Бронная улица",
        "lat": 55.7639,
        "lon": 37.5923,
        "category": "walk",
        "photo": "patriarch.jpg",
        "text": "Короткий круг вокруг пруда, потом можно зайти в кофейню рядом.",
    },
    {
        "name": "Парк «Зарядье»",
        "address": "Москва, ул. Варварка, 6",
        "lat": 55.7510,
        "lon": 37.6289,
        "category": "walk",
        "photo": "zaryadye.jpg",
        "text": "Парящий мост и вид на реку. Лучше приходить до заката.",
    },
    {
        "name": "Третьяковская галерея",
        "address": "Москва, Лаврушинский переулок, 10",
        "lat": 55.7414,
        "lon": 37.6208,
        "category": "meet",
        "photo": "tretyakov.jpg",
        "text": "Можно выбрать один-два зала и не пытаться обойти всё сразу.",
    },
    {
        "name": "ГМИИ им. А. С. Пушкина",
        "address": "Москва, ул. Волхонка, 12",
        "lat": 55.7473,
        "lon": 37.6052,
        "category": "meet",
        "photo": "pushkin.jpg",
        "text": "Удобно встретиться у входа и пойти в залы, которые открыты в этот день.",
    },
    {
        "name": "Музей «Гараж»",
        "address": "Москва, ул. Крымский Вал, 9, стр. 32",
        "lat": 55.7274,
        "lon": 37.6016,
        "category": "meet",
        "photo": "garage.jpg",
        "text": "Выставка смотрится за час, потом можно остаться в парке.",
    },
    {
        "name": "Дом Пашкова",
        "address": "Москва, ул. Воздвиженка, 3/5, стр. 1",
        "lat": 55.7496,
        "lon": 37.6086,
        "category": "study",
        "photo": "pashkov.jpg",
        "text": "Красиво даже с улицы. Рядом тихо посидеть с конспектом.",
    },
    {
        "name": "Российская государственная библиотека",
        "address": "Москва, ул. Воздвиженка, 3/5",
        "lat": 55.7517,
        "lon": 37.6094,
        "category": "study",
        "photo": "rsl.jpg",
        "text": "Если нужна тишина и розетка, лучше читать здесь, чем в кафе.",
    },
    {
        "name": "Дизайн-завод «Флакон»",
        "address": "Москва, ул. Большая Новодмитровская, 36",
        "lat": 55.8046,
        "lon": 37.5854,
        "category": "study",
        "photo": "flacon.jpg",
        "text": "Можно работать во дворе и никуда не спешить.",
    },
    {
        "name": "ВДНХ",
        "address": "Москва, проспект Мира, 119",
        "lat": 55.8263,
        "lon": 37.6379,
        "category": "walk",
        "photo": "vdnh.jpg",
        "text": "Встречаемся у главной арки и идём в ту сторону, где меньше людей.",
    },
    {
        "name": "Кулинарная лавка братьев Караваевых",
        "address": "Москва, ул. Большая Ордынка, 7",
        "lat": 55.744733,
        "lon": 37.624948,
        "category": "food",
        "photo": "karavaevy.jpg",
        "text": "Берут пироги с собой и идут гулять к Третьяковке.",
    },
]


def add_user(session: Session, username: str, display_name: str, surname: str, bio: str, password_hash: str) -> User:
    user = User(
        login=username,
        username=username,
        display_name=display_name,
        surname=surname,
        bio=bio,
        password_hash=password_hash,
    )
    session.add(user)
    session.flush()
    avatar = AVATAR_ROOT / f"{username}.jpg"
    if avatar.is_file():
        stored_name = f"{secrets.token_hex(16)}.jpg"
        (avatar_directory() / stored_name).write_bytes(avatar.read_bytes())
        user.avatar_path = stored_name
    return user


def befriend(session: Session, a: User, b: User) -> None:
    session.add_all([Friendship(user_id=a.id, friend_id=b.id), Friendship(user_id=b.id, friend_id=a.id)])


def upload_directory(kind: str) -> Path:
    path = Path(settings.upload_dir) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def avatar_directory() -> Path:
    return upload_directory("avatars")


def photo_directory() -> Path:
    return upload_directory("recommendations")


def clear_seed_photos() -> None:
    for kind in ("recommendations", "avatars"):
        directory = Path(settings.upload_dir) / kind
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)


def add_recommendations(session: Session, rng: random.Random, author: User, start: int, count: int) -> None:
    now = datetime.now(UTC)
    directory = photo_directory()
    for offset in range(count):
        venue = VENUES[(start + offset) % len(VENUES)]
        place = Place(
            name=venue["name"],
            address=venue["address"],
            lat=venue["lat"],
            lon=venue["lon"],
            created_by=author.id,
            city="Москва",
        )
        session.add(place)
        session.flush()
        recommendation = Recommendation(
            author_id=author.id,
            place_id=place.id,
            text=venue["text"],
            category=venue["category"],
            created_at=now - timedelta(minutes=rng.randint(1, 60 * 24 * 30)),
        )
        session.add(recommendation)
        session.flush()
        stored_name = f"{secrets.token_hex(16)}.jpg"
        (directory / stored_name).write_bytes((PHOTO_ROOT / venue["photo"]).read_bytes())
        session.add(RecommendationPhoto(recommendation_id=recommendation.id, stored_name=stored_name, position=0))


def seed(session: Session) -> None:
    clear_seed_photos()
    rng = random.Random(42)
    password_hash = hash_password(DEMO_PASSWORD)
    main = add_user(session, *MAIN_USER, password_hash)
    friends = [add_user(session, *row, password_hash) for row in FRIENDS]
    strangers = [add_user(session, *row, password_hash) for row in STRANGERS]

    for friend in friends:
        befriend(session, main, friend)
    for i, stranger in enumerate(strangers):
        # Strangers are friends of each other and of one of Lesha's friends, but not of Lesha:
        # friends-of-friends must stay invisible.
        befriend(session, stranger, friends[i % len(friends)])
        for other in strangers[i + 1 :]:
            befriend(session, stranger, other)

    for index, author in enumerate(friends):
        add_recommendations(session, rng, author, index * 2, RECOMMENDATIONS_PER_FRIEND)
    for index, author in enumerate(strangers):
        add_recommendations(session, rng, author, index * 3 + 1, RECOMMENDATIONS_PER_STRANGER)

    session.add(PlaceList(owner_id=main.id, title="Учёба"))
    session.commit()


def reset_and_seed() -> None:
    # Measurements and the geocoder cache are evidence for the RAT and survive a data reset.
    kept = {PerfSample.__tablename__, GeocodeCacheEntry.__tablename__}
    upgrade_to_head()
    cleared = ", ".join(t.name for t in Base.metadata.sorted_tables if t.name not in kept)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {cleared} RESTART IDENTITY CASCADE"))
    with SessionLocal() as session:
        seed(session)


if __name__ == "__main__":
    reset_and_seed()
    print(
        f"Готово: пользователь {MAIN_USER[0]}, {len(FRIENDS)} друзей по "
        f"{RECOMMENDATIONS_PER_FRIEND} рекомендаций, {len(STRANGERS)} знакомых друзей. Пароль: {DEMO_PASSWORD}"
    )
