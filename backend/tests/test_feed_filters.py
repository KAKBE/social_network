"""The feed of unseen friend recommendations, with exact city and author filters."""

from fastapi.testclient import TestClient

from app.main import app
from app.seed import DEMO_PASSWORD, reset_and_seed


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"login": username, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_unseen_friend_feed_city_and_author_filters() -> None:
    reset_and_seed()
    client = TestClient(app)
    lesha = login(client, "lesha")

    first = client.get("/api/feed", params={"limit": 200, "unseen": True}, headers=lesha)
    assert first.status_code == 200, first.text
    unseen = first.json()
    assert unseen
    assert all(not item["is_own"] for item in unseen)
    assert all(item["author"]["username"] != "stranger1" for item in unseen)
    assert [item["created_at"] for item in unseen] == sorted((item["created_at"] for item in unseen), reverse=True)
    again = client.get("/api/feed", params={"limit": 200, "unseen": True}, headers=lesha)
    assert {item["id"] for item in again.json()} == {item["id"] for item in unseen}

    opened = unseen[0]
    page = client.get(f"/api/recommendations/{opened['id']}", headers=lesha)
    assert page.status_code == 200, page.text
    after = client.get("/api/feed", params={"limit": 200, "unseen": True}, headers=lesha).json()
    assert opened["id"] not in {item["id"] for item in after}
    full = client.get("/api/feed", params={"limit": 200}, headers=lesha).json()
    assert opened["id"] in {item["id"] for item in full}

    moscow = client.get("/api/feed", params={"limit": 200, "unseen": True, "city": "Москва"}, headers=lesha).json()
    assert moscow
    assert all(item["place"]["city"] == "Москва" for item in moscow)
    assert client.get("/api/feed", params={"unseen": True, "city": "Моск"}, headers=lesha).json() == []
    assert client.get("/api/feed", params={"unseen": True, "city": "Казань"}, headers=lesha).json() == []

    anya = login(client, "anya")
    created = client.post(
        "/api/recommendations",
        json={"name": "Без города", "lat": 55.76, "lon": 37.62, "text": "Точка без города"},
        headers=anya,
    )
    assert created.status_code == 201, created.text
    bare_id = created.json()["id"]
    lesha_unseen = client.get("/api/feed", params={"limit": 200, "unseen": True}, headers=lesha).json()
    assert bare_id in {item["id"] for item in lesha_unseen}
    moscow_after = client.get(
        "/api/feed", params={"limit": 200, "unseen": True, "city": "Москва"}, headers=lesha
    ).json()
    assert bare_id not in {item["id"] for item in moscow_after}

    by_anya = client.get("/api/feed", params={"limit": 200, "unseen": True, "author": "anya"}, headers=lesha).json()
    assert by_anya
    assert all(item["author"]["username"] == "anya" for item in by_anya)
    assert bare_id in {item["id"] for item in by_anya}
    injected = client.get(
        "/api/feed", params={"unseen": True, "author": "' OR 1=1 --"}, headers=lesha
    )
    assert injected.status_code == 200
    assert injected.json() == []
    assert client.get("/api/feed", params={"unseen": True, "author": "stranger1"}, headers=lesha).json() == []

    own = client.post(
        "/api/recommendations",
        json={"name": "Своя", "lat": 55.75, "lon": 37.61, "text": "Не для своей ленты", "city": "Москва"},
        headers=lesha,
    )
    assert own.status_code == 201, own.text
    own_feed = client.get("/api/feed", params={"limit": 200, "unseen": True}, headers=lesha).json()
    assert own.json()["id"] not in {item["id"] for item in own_feed}
