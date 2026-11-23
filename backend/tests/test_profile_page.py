"""A profile shows the owner's visible recommendations, friends and mutual friends."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Friendship, User
from app.seed import reset_and_seed

PASSWORD = "Correct-horse1"


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


def publish(client: TestClient, headers: dict[str, str], name: str, **extra) -> dict:
    response = client.post(
        "/api/recommendations",
        json={"name": name, "lat": 55.75, "lon": 37.62, "text": name, **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_profile_page_respects_visibility_and_categories() -> None:
    reset_and_seed()
    client = api()
    ada = register(client, "ada_page")
    ben = register(client, "ben_page")
    cyd = register(client, "cyd_page")
    guest = register(client, "guest_page")
    befriend("ada_page", "ben_page")
    befriend("ada_page", "cyd_page")
    befriend("ben_page", "cyd_page")

    named = client.patch("/api/me", headers=ada, json={"surname": "  Страница  "})
    assert named.status_code == 200, named.text
    assert named.json()["surname"] == "Страница"
    cleared = client.patch("/api/me", headers=ada, json={"surname": "  "})
    assert cleared.json()["surname"] == ""
    client.patch("/api/me", headers=ada, json={"surname": "Страница"})

    study = publish(client, ada, "Библиотека", category="study")
    publish(client, ada, "Только близким", category="walk", visibility="close")
    draft = publish(client, ada, "Черновик еды", category="food", draft=True)
    rejected = publish_raw(client, ada, category="shop")
    assert rejected.status_code == 422

    ada_id = client.get("/api/me", headers=ada).json()["public_id"]
    hidden = client.get(f"/api/users/{ada_id}", headers=guest).json()
    assert hidden["surname"] == "Страница"
    assert hidden["friend_count"] is None
    assert hidden["friends"] == []
    assert hidden["mutual"] == []
    assert client.get(f"/api/users/{ada_id}/recommendations", headers=guest).json() == []

    seen = client.get(f"/api/users/{ada_id}", headers=ben).json()
    assert seen["friend_count"] == 2
    assert {person["username"] for person in seen["friends"]} == {"ben_page", "cyd_page"}
    assert [person["username"] for person in seen["mutual"]] == ["cyd_page"]

    ben_posts = client.get(f"/api/users/{ada_id}/recommendations", headers=ben).json()
    assert [item["id"] for item in ben_posts] == [study["id"]]
    assert ben_posts[0]["category"] == "study"
    filtered = client.get(f"/api/users/{ada_id}/recommendations", params={"category": "food"}, headers=ben)
    assert filtered.status_code == 200, filtered.text
    assert filtered.json() == []
    bad = client.get(f"/api/users/{ada_id}/recommendations", params={"category": "shop"}, headers=ben)
    assert bad.status_code == 422

    own = client.get(f"/api/users/{ada_id}/recommendations", headers=ada).json()
    assert {item["id"] for item in own} == {study["id"], draft["id"], own_close_id(own)}
    assert draft["id"] in {item["id"] for item in own if item["status"] == "draft"}


def own_close_id(rows: list[dict]) -> int:
    return next(item["id"] for item in rows if item["category"] == "walk")


def publish_raw(client: TestClient, headers: dict[str, str], **extra):
    return client.post(
        "/api/recommendations",
        json={"name": "Нет", "lat": 55.7, "lon": 37.6, "text": "Нет", **extra},
        headers=headers,
    )
