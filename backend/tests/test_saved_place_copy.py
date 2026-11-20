"""A saved place stays as a name and a point after the recommendation is hidden or deleted."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Place, Recommendation
from app.seed import DEMO_PASSWORD, reset_and_seed


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"login": username, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_hidden_or_deleted_recommendation_leaves_a_place_copy() -> None:
    reset_and_seed()
    client = TestClient(app)
    anya = login(client, "anya")
    lesha = login(client, "lesha")
    created = client.post(
        "/api/recommendations",
        json={
            "name": "Тихая кофейня",
            "address": "Москва, переулок",
            "lat": 55.76,
            "lon": 37.62,
            "text": "Секретный текст рекомендации",
        },
        headers=anya,
    )
    assert created.status_code == 201, created.text
    place_id = created.json()["place"]["id"]
    study = next(item for item in client.get("/api/lists", headers=lesha).json() if item["title"] == "Учёба")
    saved = client.post(f"/api/lists/{study['id']}/places", json={"place_id": place_id}, headers=lesha)
    assert saved.status_code == 200, saved.text
    place = next(item for item in saved.json()["places"] if item["id"] == place_id)
    assert place["limited"] is False
    assert place["name"] == "Тихая кофейня"

    with SessionLocal() as session:
        live = session.get(Place, place_id)
        live.name = "Переименовано после сохранения"
        live.address = "Другой адрес"
        recommendation = session.scalar(select(Recommendation).where(Recommendation.place_id == place_id))
        recommendation.visibility = "close"
        session.commit()
        recommendation_id = recommendation.id

    hidden = client.get("/api/lists", headers=lesha).json()
    copied = next(item for row in hidden if row["title"] == "Учёба" for item in row["places"] if item["item_id"] == place["item_id"])
    assert copied["limited"] is True
    assert copied["id"] == place_id
    assert copied["name"] == "Тихая кофейня"
    assert copied["address"] == "Москва, переулок"
    assert round(copied["lat"], 5) == 55.76
    assert round(copied["lon"], 5) == 37.62
    assert "author" not in copied
    assert "text" not in copied
    assert "photos" not in copied
    assert "Секретный текст рекомендации" not in str(hidden)
    assert client.get(f"/api/recommendations/{recommendation_id}", headers=lesha).status_code == 404
    feed = client.get("/api/feed", params={"limit": 200, "unseen": True}, headers=lesha).json()
    assert recommendation_id not in {item["id"] for item in feed}

    with SessionLocal() as session:
        session.delete(session.get(Place, place_id))
        session.commit()

    after_delete = client.get("/api/lists", headers=lesha).json()
    surviving = next(
        item for row in after_delete if row["title"] == "Учёба" for item in row["places"] if item["name"] == "Тихая кофейня"
    )
    assert surviving["limited"] is True
    assert surviving["id"] is None
    assert surviving["address"] == "Москва, переулок"
    assert round(surviving["lat"], 5) == 55.76
    assert round(surviving["lon"], 5) == 37.62
    removed = client.delete(f"/api/lists/{study['id']}/items/{surviving['item_id']}", headers=lesha)
    assert removed.status_code == 200, removed.text
    assert "Тихая кофейня" not in {item["name"] for item in removed.json()["places"]}
