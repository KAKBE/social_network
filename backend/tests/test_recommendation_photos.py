"""Recommendation photos: at most five checked images, visible only with the recommendation."""

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import RecommendationPhoto
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


def test_recommendation_photos_are_checked_and_private() -> None:
    reset_and_seed()
    client = api()
    lesha = login(client, "lesha")
    anya = login(client, "anya")
    stranger = login(client, "stranger1")
    created = client.post(
        "/api/recommendations",
        json={"name": "С фото", "lat": 55.75, "lon": 37.6, "text": "С фото", "visibility": "close"},
        headers=lesha,
    )
    assert created.status_code == 201, created.text
    rec_id = created.json()["id"]

    rejected = client.post(
        f"/api/recommendations/{rec_id}/photos",
        headers=lesha,
        files={"file": ("note.exe", PNG_1X1, "application/octet-stream")},
    )
    assert rejected.status_code == 422
    gif = client.post(
        f"/api/recommendations/{rec_id}/photos",
        headers=lesha,
        files={"file": ("pic.gif", b"GIF89a", "image/gif")},
    )
    assert gif.status_code == 422

    uploaded = None
    for index in range(5):
        uploaded = client.post(
            f"/api/recommendations/{rec_id}/photos",
            headers=lesha,
            files={"file": (f"pic{index}.png", PNG_1X1, "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
    assert len(uploaded.json()["photos"]) == 5
    extra = client.post(
        f"/api/recommendations/{rec_id}/photos",
        headers=lesha,
        files={"file": ("pic5.png", PNG_1X1, "image/png")},
    )
    assert extra.status_code == 422

    photo_id = uploaded.json()["photos"][0]["id"]
    with SessionLocal() as session:
        previous_name = session.get(RecommendationPhoto, photo_id).stored_name
    previous_path = Path(settings.upload_dir, "recommendations", previous_name)
    assert previous_path.is_file()
    replaced_bytes = PNG_1X1[:-1] + bytes([PNG_1X1[-1] ^ 0x01])
    replaced = client.put(
        f"/api/recommendations/{rec_id}/photos/{photo_id}",
        headers=lesha,
        files={"file": ("next.png", replaced_bytes, "image/png")},
    )
    assert replaced.status_code == 200, replaced.text
    assert len(replaced.json()["photos"]) == 5
    assert photo_id in {item["id"] for item in replaced.json()["photos"]}
    assert not previous_path.is_file()
    own = client.get(f"/api/recommendations/{rec_id}/photos/{photo_id}", headers=lesha)
    assert own.status_code == 200
    assert own.headers["cache-control"] == "no-store"
    assert own.content == replaced_bytes
    assert client.post(
        f"/api/recommendations/{rec_id}/photos",
        headers=anya,
        files={"file": ("pic.png", PNG_1X1, "image/png")},
    ).status_code == 404
    assert client.get(f"/api/recommendations/{rec_id}/photos/{photo_id}", headers=anya).status_code == 404
    assert client.get(f"/api/recommendations/{rec_id}/photos/{photo_id}", headers=stranger).status_code == 404

    client.put("/api/friends/anya/close", json={"close": True}, headers=lesha)
    assert client.get(f"/api/recommendations/{rec_id}/photos/{photo_id}", headers=anya).content == replaced_bytes
    forbidden = client.put(
        f"/api/recommendations/{rec_id}/photos/{photo_id}",
        headers=anya,
        files={"file": ("next.png", PNG_1X1, "image/png")},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Фото меняет автор"
    assert client.post(
        f"/api/recommendations/{rec_id}/photos",
        headers=anya,
        files={"file": ("pic.png", PNG_1X1, "image/png")},
    ).status_code == 403
