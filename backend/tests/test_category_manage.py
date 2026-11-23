"""The author can hide, retarget or remove a category without touching anyone else's posts."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.models import Friendship, NotificationJob, RecommendationAudience, User
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


def names(client: TestClient, headers: dict[str, str], public_id: str) -> list[str]:
    rows = client.get(f"/api/users/{public_id}/recommendations", headers=headers).json()
    return [row["text"] for row in rows]


def test_author_manages_a_category_and_an_empty_one_disappears() -> None:
    reset_and_seed()
    client = api()
    ada = register(client, "ada_cat")
    ben = register(client, "ben_cat")
    guest = register(client, "guest_cat")
    befriend("ada_cat", "ben_cat")
    ada_id = client.get("/api/me", headers=ada).json()["public_id"]

    walk = publish(client, ada, "Прогулка Ады", visibility="everyone", category="walk")
    limited = publish(
        client, ada, "Закрытая прогулка", visibility="allow", category="walk", audience=["ben_cat"]
    )
    draft = publish(client, ada, "Черновик прогулки", visibility="friends", category="walk", draft=True)
    other = publish(client, ada, "Еда Ады", visibility="friends", category="food")
    publish(client, ben, "Прогулка Бена", visibility="friends", category="walk")

    walk_ids = [walk["id"], limited["id"], draft["id"]]
    with SessionLocal() as session:
        jobs_before = session.scalar(
            select(func.count()).select_from(NotificationJob).where(NotificationJob.recommendation_id.in_(walk_ids))
        )

    hidden = client.post("/api/me/categories/walk", json={"action": "visibility", "visibility": "self"}, headers=ada)
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["changed"] == 3
    limited_after = client.get(f"/api/recommendations/{limited['id']}", headers=ada).json()
    assert limited_after["visibility"] == "self"
    assert limited_after["audience"] == []
    with SessionLocal() as session:
        audience_left = session.scalar(
            select(func.count())
            .select_from(RecommendationAudience)
            .where(RecommendationAudience.recommendation_id == limited["id"])
        )
        jobs_after = session.scalar(
            select(func.count()).select_from(NotificationJob).where(NotificationJob.recommendation_id.in_(walk_ids))
        )
    assert audience_left == 0
    assert jobs_after == jobs_before
    draft_after = client.get(f"/api/recommendations/{draft['id']}", headers=ada).json()
    assert draft_after["status"] == "draft"
    assert draft_after["visibility"] == "self"
    assert client.get(f"/api/recommendations/{walk['id']}", headers=ben).status_code == 404
    assert client.get(f"/api/recommendations/{limited['id']}", headers=ben).status_code == 404
    assert client.get(f"/api/recommendations/{walk['id']}", headers=guest).status_code == 404
    assert client.get(f"/api/recommendations/{walk['id']}", headers=ada).json()["visibility"] == "self"
    assert "Прогулка Ады" in names(client, ada, ada_id)
    assert "Прогулка Ады" not in names(client, guest, ada_id)
    assert "Еда Ады" in names(client, ben, ada_id)
    assert "Прогулка Бена" in names(client, ben, client.get("/api/me", headers=ben).json()["public_id"])

    shown = client.post(
        "/api/me/categories/walk", json={"action": "visibility", "visibility": "everyone"}, headers=ada
    )
    assert shown.status_code == 200, shown.text
    assert "Прогулка Ады" in names(client, guest, ada_id)
    guest_feed = client.get("/api/feed", params={"limit": 200}, headers=guest).json()
    assert all(item["id"] != walk["id"] for item in guest_feed)

    cleared = client.post("/api/me/categories/food", json={"action": "clear"}, headers=ada)
    assert cleared.status_code == 200, cleared.text
    kept = client.get(f"/api/recommendations/{other['id']}", headers=ada).json()
    assert kept["category"] == ""
    assert kept["text"] == "Еда Ады"
    food = client.get(f"/api/users/{ada_id}/recommendations", params={"category": "food"}, headers=ada).json()
    assert food == []

    study = publish(client, ada, "Учёба Ады", category="study")
    removed = client.post("/api/me/categories/study", json={"action": "delete"}, headers=ada)
    assert removed.status_code == 200, removed.text
    assert client.get(f"/api/recommendations/{study['id']}", headers=ada).status_code == 404
    assert client.post("/api/me/categories/study", json={"action": "clear"}, headers=ada).status_code == 404
    assert client.post("/api/me/categories/nope", json={"action": "clear"}, headers=ada).status_code == 404

    last = publish(client, ada, "Последняя еда", category="food")
    assert client.delete(f"/api/recommendations/{last['id']}", headers=ada).status_code == 204
    again = client.get(f"/api/users/{ada_id}/recommendations", params={"category": "food"}, headers=ada).json()
    assert again == []
