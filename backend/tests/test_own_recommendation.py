"""The author can edit and delete a recommendation. Anyone else cannot change it."""

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.seed import DEMO_PASSWORD, reset_and_seed

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def api() -> TestClient:
    return TestClient(app)


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"login": username, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_author_edits_and_deletes_while_others_cannot() -> None:
    reset_and_seed()
    client = api()
    anya = login(client, "anya")
    lesha = login(client, "lesha")
    sasha = login(client, "sasha")
    stranger = login(client, "stranger1")

    created = client.post(
        "/api/recommendations",
        json={
            "name": "Тихая кофейня",
            "address": "улица Тестовая, 1",
            "lat": 55.751,
            "lon": 37.618,
            "text": "Секретный текст",
        },
        headers=anya,
    )
    assert created.status_code == 201, created.text
    rec = created.json()
    rec_id = rec["id"]
    place_id = rec["place"]["id"]

    folder = Path(settings.upload_dir, "recommendations")
    before = set(folder.glob("*.png"))
    photo = client.post(
        f"/api/recommendations/{rec_id}/photos",
        files={"file": ("place.png", PNG_1X1, "image/png")},
        headers=anya,
    )
    assert photo.status_code == 200, photo.text
    added = set(folder.glob("*.png")) - before
    assert len(added) == 1
    stored_photo = added.pop()

    study = client.post("/api/lists", json={"title": "Учёба"}, headers=lesha)
    assert study.status_code == 201, study.text
    saved = client.post(
        f"/api/lists/{study.json()['id']}/places",
        json={"place_id": place_id},
        headers=lesha,
    )
    assert saved.status_code == 200, saved.text

    unchanged = {
        "name": "Тихая кофейня",
        "text": "Секретный текст",
        "visibility": "deny",
        "audience": ["lesha"],
    }
    for headers, code in ((lesha, 403), (sasha, 404)):
        denied = client.patch(f"/api/recommendations/{rec_id}", json=unchanged, headers=headers)
        assert denied.status_code == code, denied.text
        still = client.get(f"/api/recommendations/{rec_id}", headers=anya).json()
        assert still["text"] == "Секретный текст"
        assert still["place"]["name"] == "Тихая кофейня"
        assert still["visibility"] == "friends"

    edited = client.patch(
        f"/api/recommendations/{rec_id}",
        json={"name": "Новое имя", "text": "Другой текст", "visibility": "deny", "audience": ["lesha"]},
        headers=anya,
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["text"] == "Другой текст"
    assert body["place"]["name"] == "Новое имя"
    assert body["place"]["address"] == "улица Тестовая, 1"
    assert body["visibility"] == "deny"
    assert body["audience"] == ["lesha"]
    visible = client.get(f"/api/recommendations/{rec_id}", headers=stranger)
    assert visible.status_code == 200
    seen = visible.json()
    assert seen["audience"] == []
    assert seen["text"] == "Другой текст"
    assert seen["place"]["name"] == "Новое имя"
    assert client.get(f"/api/recommendations/{rec_id}", headers=lesha).status_code == 404
    assert client.get(f"/api/recommendations/{rec_id}", headers=sasha).status_code == 404

    outsider = client.patch(
        f"/api/recommendations/{rec_id}",
        json={"name": "Чужой", "text": "нет", "visibility": "allow", "audience": ["sasha"]},
        headers=anya,
    )
    assert outsider.status_code == 422
    assert client.get(f"/api/recommendations/{rec_id}", headers=anya).json()["text"] == "Другой текст"

    hidden = client.get("/api/lists", headers=lesha).json()[0]["places"][0]
    assert hidden["name"] == "Тихая кофейня"
    assert hidden["address"] == "улица Тестовая, 1"
    assert hidden["id"] == place_id
    assert hidden["limited"] is True

    for headers, code in ((stranger, 403), (sasha, 404)):
        denied = client.delete(f"/api/recommendations/{rec_id}", headers=headers)
        assert denied.status_code == code, denied.text
        assert client.get(f"/api/recommendations/{rec_id}", headers=anya).status_code == 200

    removed = client.delete(f"/api/recommendations/{rec_id}", headers=anya)
    assert removed.status_code == 204, removed.text
    assert client.get(f"/api/recommendations/{rec_id}", headers=anya).status_code == 404
    assert client.get(f"/api/recommendations/{rec_id}/photos/{photo.json()['photos'][0]['id']}", headers=anya).status_code == 404
    assert not stored_photo.exists()
    feed = client.get("/api/feed", params={"limit": 200}, headers=lesha)
    assert rec_id not in {item["id"] for item in feed.json()}

    copied = client.get("/api/lists", headers=lesha).json()[0]["places"][0]
    assert copied["name"] == "Тихая кофейня"
    assert copied["address"] == "улица Тестовая, 1"
    assert round(copied["lat"], 5) == 55.751
    assert round(copied["lon"], 5) == 37.618
    assert copied["id"] is None
    assert copied["limited"] is True
    assert "author" not in copied
    assert "text" not in copied
    assert "photos" not in copied
