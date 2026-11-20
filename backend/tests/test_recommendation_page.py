"""Opening a recommendation: only a viewer who may see it can like it."""

from fastapi.testclient import TestClient

from app.main import app
from app.seed import DEMO_PASSWORD, reset_and_seed


def api() -> TestClient:
    return TestClient(app)


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"login": username, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_like_requires_visibility_and_toggles() -> None:
    reset_and_seed()
    client = api()
    lesha = login(client, "lesha")
    stranger = login(client, "stranger1")
    item = next(row for row in client.get("/api/feed", params={"limit": 200}, headers=lesha).json() if not row["is_own"])
    assert item["author"]["public_id"]
    assert item["liked"] is False

    liked = client.post(f"/api/recommendations/{item['id']}/like", headers=lesha)
    assert liked.status_code == 200, liked.text
    assert liked.json()["liked"] is True
    assert liked.json()["like_count"] == 1

    page = client.get(f"/api/recommendations/{item['id']}", headers=lesha)
    assert page.json()["liked"] is True
    assert page.json()["place"]["name"] == item["place"]["name"]

    hidden = client.post(f"/api/recommendations/{item['id']}/like", headers=stranger)
    assert hidden.status_code == 404

    again = client.post(f"/api/recommendations/{item['id']}/like", headers=lesha)
    assert again.json()["liked"] is False
    assert again.json()["like_count"] == 0
