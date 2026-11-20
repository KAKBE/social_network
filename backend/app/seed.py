"""Brings the schema to the latest migration, clears user data and loads synthetic test data.

All places are synthetic points inside central Moscow named "Тестовое место"; they are not real
recommendations and must not be presented as user data. Each place gets one real
photograph of that kind of place. Credits are in app/seed_photos/SOURCES.txt.
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
MAIN_USER = ("lesha", "Лёша")
FRIENDS = [("anya", "Аня"), ("sasha", "Саша"), ("kristina", "Кристина"), ("dima", "Дима"), ("masha", "Маша")]
STRANGERS = [("stranger1", "Посторонний 1"), ("stranger2", "Посторонний 2"), ("stranger3", "Посторонний 3")]
RECOMMENDATIONS_PER_FRIEND = 10
RECOMMENDATIONS_PER_STRANGER = 10
CATEGORIES = ["кофейня", "коворкинг", "парк", "кафе", "библиотека", "выставка", "бар", "антикафе"]
CATEGORY_PHOTO = {
    "кофейня": "coffee.jpg",
    "коворкинг": "cowork.jpg",
    "парк": "park.jpg",
    "кафе": "cafe.jpg",
    "библиотека": "library.jpg",
    "выставка": "exhibit.jpg",
    "бар": "bar.jpg",
    "антикафе": "anticafe.jpg",
}
PHOTO_ROOT = Path(__file__).resolve().parent / "seed_photos"
TEXTS = [
    "Тихо, есть розетки, удобно готовиться к семинарам.",
    "Хорошее место, чтобы встретиться после пар.",
    "Были с друзьями в выходные, советую.",
    "Уютно, недорого, можно сидеть долго.",
    "Отличное место для свидания вечером.",
]
CENTER_BOX = (55.70, 55.80, 37.50, 37.70)


def add_user(session: Session, username: str, display_name: str, password_hash: str) -> User:
    user = User(login=username, username=username, display_name=display_name, password_hash=password_hash)
    session.add(user)
    session.flush()
    return user


def befriend(session: Session, a: User, b: User) -> None:
    session.add_all([Friendship(user_id=a.id, friend_id=b.id), Friendship(user_id=b.id, friend_id=a.id)])


def photo_directory() -> Path:
    path = Path(settings.upload_dir) / "recommendations"
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_seed_photos() -> None:
    directory = Path(settings.upload_dir) / "recommendations"
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)


def add_recommendations(session: Session, rng: random.Random, author: User, count: int, counter: list[int]) -> None:
    now = datetime.now(UTC)
    directory = photo_directory()
    for _ in range(count):
        counter[0] += 1
        category = rng.choice(CATEGORIES)
        lat_min, lat_max, lon_min, lon_max = CENTER_BOX
        place = Place(
            name=f"Тестовое место №{counter[0]} ({category})",
            address="синтетические тестовые данные",
            lat=round(rng.uniform(lat_min, lat_max), 6),
            lon=round(rng.uniform(lon_min, lon_max), 6),
            created_by=author.id,
            city="Москва",
        )
        session.add(place)
        session.flush()
        recommendation = Recommendation(
            author_id=author.id,
            place_id=place.id,
            text=rng.choice(TEXTS),
            created_at=now - timedelta(minutes=rng.randint(1, 60 * 24 * 30)),
        )
        session.add(recommendation)
        session.flush()
        stored_name = f"{secrets.token_hex(16)}.jpg"
        (directory / stored_name).write_bytes((PHOTO_ROOT / CATEGORY_PHOTO[category]).read_bytes())
        session.add(
            RecommendationPhoto(recommendation_id=recommendation.id, stored_name=stored_name, position=0)
        )


def seed(session: Session) -> None:
    clear_seed_photos()
    rng = random.Random(42)
    password_hash = hash_password(DEMO_PASSWORD)
    main = add_user(session, *MAIN_USER, password_hash)
    friends = [add_user(session, u, n, password_hash) for u, n in FRIENDS]
    strangers = [add_user(session, u, n, password_hash) for u, n in STRANGERS]

    for friend in friends:
        befriend(session, main, friend)
    for i, stranger in enumerate(strangers):
        # Strangers are friends of each other and of one of Lesha's friends, but not of Lesha:
        # friends-of-friends must stay invisible.
        befriend(session, stranger, friends[i % len(friends)])
        for other in strangers[i + 1 :]:
            befriend(session, stranger, other)

    counter = [0]
    for friend in friends:
        add_recommendations(session, rng, friend, RECOMMENDATIONS_PER_FRIEND, counter)
    for stranger in strangers:
        add_recommendations(session, rng, stranger, RECOMMENDATIONS_PER_STRANGER, counter)

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
        f"{RECOMMENDATIONS_PER_FRIEND} рекомендаций, {len(STRANGERS)} посторонних. Пароль: {DEMO_PASSWORD}"
    )
