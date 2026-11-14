"""Brings the schema to the latest migration, clears user data and loads synthetic test data.

All places are synthetic points inside central Moscow named "Тестовое место"; they are not real
recommendations and must not be presented as user data.
"""

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.migrations import upgrade_to_head
from app.models import (
    Friendship,
    GeocodeCacheEntry,
    PerfSample,
    Place,
    PlaceList,
    Recommendation,
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
TEXTS = [
    "Тихо, есть розетки, удобно готовиться к семинарам.",
    "Хорошее место, чтобы встретиться после пар.",
    "Были с друзьями в выходные, советую.",
    "Уютно, недорого, можно сидеть долго.",
    "Отличное место для свидания вечером.",
]
CENTER_BOX = (55.70, 55.80, 37.50, 37.70)


def add_user(session: Session, username: str, display_name: str, password_hash: str) -> User:
    user = User(username=username, display_name=display_name, password_hash=password_hash)
    session.add(user)
    session.flush()
    return user


def befriend(session: Session, a: User, b: User) -> None:
    session.add_all([Friendship(user_id=a.id, friend_id=b.id), Friendship(user_id=b.id, friend_id=a.id)])


def add_recommendations(session: Session, rng: random.Random, author: User, count: int, counter: list[int]) -> None:
    now = datetime.now(UTC)
    for _ in range(count):
        counter[0] += 1
        lat_min, lat_max, lon_min, lon_max = CENTER_BOX
        place = Place(
            name=f"Тестовое место №{counter[0]} ({rng.choice(CATEGORIES)})",
            address="синтетические тестовые данные",
            lat=round(rng.uniform(lat_min, lat_max), 6),
            lon=round(rng.uniform(lon_min, lon_max), 6),
            created_by=author.id,
        )
        session.add(place)
        session.flush()
        session.add(
            Recommendation(
                author_id=author.id,
                place_id=place.id,
                text=rng.choice(TEXTS),
                created_at=now - timedelta(minutes=rng.randint(1, 60 * 24 * 30)),
            )
        )


def seed(session: Session) -> None:
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
