"""RAT criterion K3: a user sees 100% of friends' recommendations and none from non-friends."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Friendship, PlaceList, Recommendation, User
from app.seed import DEMO_PASSWORD, RECOMMENDATIONS_PER_FRIEND, FRIENDS, reset_and_seed


@pytest.fixture(scope="module")
def client() -> TestClient:
    reset_and_seed()
    return TestClient(app)


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"login": username, "password": DEMO_PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def user_id(username: str) -> int:
    with SessionLocal() as session:
        return session.scalar(select(User.id).where(User.username == username))


def recommendation_ids_by(author_ids: set[int]) -> set[int]:
    with SessionLocal() as session:
        return set(session.scalars(select(Recommendation.id).where(Recommendation.author_id.in_(author_ids))))


def friend_ids(uid: int) -> set[int]:
    with SessionLocal() as session:
        return set(session.scalars(select(Friendship.friend_id).where(Friendship.user_id == uid)))


def test_feed_requires_login(client: TestClient) -> None:
    assert client.get("/api/feed").status_code == 401


def test_feed_contains_all_friend_recommendations_and_no_others(client: TestClient) -> None:
    headers = login(client, "lesha")
    lesha = user_id("lesha")
    friends = friend_ids(lesha)

    feed = client.get("/api/feed", params={"limit": 200}, headers=headers).json()
    seen = {item["id"] for item in feed}

    expected = recommendation_ids_by(friends | {lesha})
    with SessionLocal() as session:
        all_ids = set(session.scalars(select(Recommendation.id)))
    others = all_ids - expected

    assert len(friends) == len(FRIENDS)
    assert len(recommendation_ids_by(friends)) == len(FRIENDS) * RECOMMENDATIONS_PER_FRIEND
    assert others, "test data must contain recommendations of non-friends"
    assert seen == expected
    assert seen.isdisjoint(others)


def test_friends_of_friends_are_not_visible(client: TestClient) -> None:
    headers = login(client, "lesha")
    stranger1 = user_id("stranger1")
    anya = user_id("anya")
    assert stranger1 in friend_ids(anya), "stranger1 must be a friend of Lesha's friend"

    feed = client.get("/api/feed", params={"limit": 200}, headers=headers).json()
    assert all(item["author"]["id"] != stranger1 for item in feed)


def test_new_recommendation_visible_to_friends_only(client: TestClient) -> None:
    lesha_headers = login(client, "lesha")
    created = client.post(
        "/api/recommendations",
        json={"name": "Проверочное место", "lat": 55.75, "lon": 37.6, "text": "Проверка доступа"},
        headers=lesha_headers,
    )
    assert created.status_code == 201
    rec_id = created.json()["id"]

    anya_feed = client.get("/api/feed", params={"limit": 200}, headers=login(client, "anya")).json()
    stranger_feed = client.get("/api/feed", params={"limit": 200}, headers=login(client, "stranger1")).json()

    assert rec_id in {item["id"] for item in anya_feed}
    assert rec_id not in {item["id"] for item in stranger_feed}


def test_cannot_save_invisible_place_or_use_foreign_list(client: TestClient) -> None:
    headers = login(client, "lesha")
    lists = client.get("/api/lists", headers=headers).json()
    study = next(pl for pl in lists if pl["title"] == "Учёба")

    with SessionLocal() as session:
        stranger_place_id = session.scalar(
            select(Recommendation.place_id).where(Recommendation.author_id == user_id("stranger2"))
        )
        anya_list = PlaceList(owner_id=user_id("anya"), title="Чужой список")
        session.add(anya_list)
        session.commit()
        anya_list_id = anya_list.id

    response = client.post(f"/api/lists/{study['id']}/places", json={"place_id": stranger_place_id}, headers=headers)
    assert response.status_code == 404

    friend_place_id = client.get("/api/feed", headers=headers).json()[0]["place"]["id"]
    response = client.post(f"/api/lists/{anya_list_id}/places", json={"place_id": friend_place_id}, headers=headers)
    assert response.status_code == 404


def test_save_friend_place_to_study_list(client: TestClient) -> None:
    headers = login(client, "lesha")
    study = next(pl for pl in client.get("/api/lists", headers=headers).json() if pl["title"] == "Учёба")
    friend_item = next(item for item in client.get("/api/feed", headers=headers).json() if not item["is_own"])

    response = client.post(
        f"/api/lists/{study['id']}/places", json={"place_id": friend_item["place"]["id"]}, headers=headers
    )
    assert response.status_code == 200
    assert friend_item["place"]["id"] in {p["id"] for p in response.json()["places"]}
