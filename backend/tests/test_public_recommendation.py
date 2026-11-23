"""«Все» is readable on the author's profile and stays off a stranger's map, feed and lists."""

import base64
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Friendship, User
from app.notify import recipient_ids
from app.seed import reset_and_seed

PASSWORD = "Correct-horse1"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def api() -> TestClient:
    return TestClient(app)


def register(client: TestClient, login: str) -> dict[str, str]:
    created = client.post(
        "/api/auth/register",
        json={"login": login, "password": PASSWORD, "display_name": login, "username": login},
    )
    assert created.status_code == 201, created.text
    return {"Authorization": f"Bearer {created.json()['token']}"}


def befriend(left: str, right: str) -> None:
    with SessionLocal() as session:
        a = session.scalar(select(User).where(User.login == left))
        b = session.scalar(select(User).where(User.login == right))
        session.add(Friendship(user_id=a.id, friend_id=b.id))
        session.add(Friendship(user_id=b.id, friend_id=a.id))
        session.commit()


def user_id(login: str) -> int:
    with SessionLocal() as session:
        return session.scalar(select(User.id).where(User.login == login))


def publish(client: TestClient, headers: dict[str, str], name: str, **extra) -> dict:
    response = client.post(
        "/api/recommendations",
        json={"name": name, "lat": 55.75, "lon": 37.62, "text": name, **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_everyone_post_is_on_the_profile_and_off_a_strangers_map() -> None:
    reset_and_seed()
    client = api()
    ada = register(client, "ada_public")
    ben = register(client, "ben_public")
    guest = register(client, "guest_public")
    befriend("ada_public", "ben_public")
    profile = client.get("/api/me", headers=ada).json()["public_id"]

    public = publish(client, ada, "Для всех", visibility="everyone", category="walk")
    friends_only = publish(client, ada, "Только друзьям", visibility="friends")
    publish(client, ada, "Черновик для всех", visibility="everyone", draft=True)
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    publish(client, ada, "Позже для всех", visibility="everyone", publish_at=future)
    rejected = client.post(
        "/api/recommendations",
        json={
            "name": "Лишний список",
            "lat": 55.75,
            "lon": 37.62,
            "text": "Лишний список",
            "visibility": "everyone",
            "audience": ["ben_public"],
        },
        headers=ada,
    )
    assert rejected.status_code == 422

    photo = client.post(
        f"/api/recommendations/{public['id']}/photos",
        files={"file": ("dot.png", PNG_1X1, "image/png")},
        headers=ada,
    )
    assert photo.status_code == 200, photo.text
    photo_id = photo.json()["photos"][0]["id"]

    guest_profile = client.get(f"/api/users/{profile}/recommendations", headers=guest).json()
    assert [item["text"] for item in guest_profile] == ["Для всех"]
    assert guest_profile[0]["on_map"] is False
    assert guest_profile[0]["place"]["lat"] == 55.75

    guest_feed = client.get("/api/feed", params={"limit": 200}, headers=guest).json()
    assert public["id"] not in {item["id"] for item in guest_feed}

    opened = client.get(f"/api/recommendations/{public['id']}", headers=guest)
    assert opened.status_code == 200
    assert opened.json()["on_map"] is False
    assert client.get(f"/api/recommendations/{friends_only['id']}", headers=guest).status_code == 404
    assert (
        client.get(f"/api/recommendations/{public['id']}/photos/{photo_id}", headers=guest).content == PNG_1X1
    )

    saved = client.post("/api/lists", json={"title": "Моё"}, headers=guest)
    assert saved.status_code == 201, saved.text
    listed = client.post(
        f"/api/lists/{saved.json()['id']}/places",
        json={"place_id": public["place"]["id"]},
        headers=guest,
    )
    assert listed.status_code == 404
    assert client.post(f"/api/recommendations/{public['id']}/like", headers=guest).status_code == 404

    friend_feed = client.get("/api/feed", params={"limit": 200}, headers=ben).json()
    friend_item = next(item for item in friend_feed if item["id"] == public["id"])
    assert friend_item["on_map"] is True
    assert "Позже для всех" not in {item["text"] for item in friend_feed}
    with SessionLocal() as session:
        recipients = recipient_ids(session, public["id"])
    assert user_id("ben_public") in recipients
    assert user_id("guest_public") not in recipients

    hidden = client.patch(
        f"/api/recommendations/{public['id']}",
        json={"name": "Для всех", "text": "Для всех", "visibility": "friends", "category": "walk"},
        headers=ada,
    )
    assert hidden.status_code == 200, hidden.text
    after = client.get(f"/api/users/{profile}/recommendations", headers=guest).json()
    assert after == []
    assert client.get(f"/api/recommendations/{public['id']}", headers=guest).status_code == 404
