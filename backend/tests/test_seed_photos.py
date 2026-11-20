"""Seeded places carry a real photograph that a friend can open."""

from fastapi.testclient import TestClient

from app.images import inspect_image
from app.main import app
from app.seed import DEMO_PASSWORD, reset_and_seed


def test_seed_place_photo_is_visible_to_a_friend() -> None:
    reset_and_seed()
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"login": "lesha", "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    feed = client.get("/api/feed", params={"limit": 200}, headers=headers)
    assert feed.status_code == 200, feed.text
    item = next(row for row in feed.json() if not row["is_own"])
    assert len(item["photos"]) == 1
    photo = client.get(f"/api/recommendations/{item['id']}/photos/{item['photos'][0]['id']}", headers=headers)
    assert photo.status_code == 200
    assert photo.content.startswith(b"\xff\xd8\xff")
    assert inspect_image(photo.content) == "jpg"
