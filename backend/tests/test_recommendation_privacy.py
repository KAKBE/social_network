"""A recommendation stays hidden from anyone outside the author's rule."""

from fastapi.testclient import TestClient

from app.main import app
from app.seed import DEMO_PASSWORD, reset_and_seed


def api() -> TestClient:
    return TestClient(app)


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"login": username, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def publish(client: TestClient, headers: dict[str, str], name: str, **extra: object) -> dict:
    body = {"name": name, "lat": 55.75, "lon": 37.6, "text": name, **extra}
    created = client.post("/api/recommendations", json=body, headers=headers)
    assert created.status_code == 201, created.text
    return created.json()


def seen(client: TestClient, headers: dict[str, str], rec_id: int) -> tuple[bool, int]:
    feed = client.get("/api/feed", params={"limit": 200}, headers=headers)
    assert feed.status_code == 200, feed.text
    in_feed = rec_id in {item["id"] for item in feed.json()}
    direct = client.get(f"/api/recommendations/{rec_id}", headers=headers)
    return in_feed, direct.status_code


def test_recommendation_visibility_rules() -> None:
    reset_and_seed()
    client = api()
    lesha = login(client, "lesha")
    anya = login(client, "anya")
    sasha = login(client, "sasha")
    stranger = login(client, "stranger1")

    assert client.put("/api/friends/stranger1/close", json={"close": True}, headers=lesha).status_code == 404
    assert client.put("/api/friends/anya/close", json={"close": True}, headers=lesha).status_code == 204
    friends = client.get("/api/friends", headers=lesha).json()
    assert next(item for item in friends if item["username"] == "anya")["is_close"] is True
    assert next(item for item in friends if item["username"] == "sasha")["is_close"] is False

    close = publish(client, lesha, "Только близким", visibility="close")
    assert seen(client, lesha, close["id"]) == (True, 200)
    assert seen(client, anya, close["id"]) == (True, 200)
    assert seen(client, sasha, close["id"]) == (False, 404)
    assert seen(client, stranger, close["id"]) == (False, 404)

    denied = publish(client, lesha, "Кроме Саши", visibility="deny", audience=["sasha"])
    assert seen(client, anya, denied["id"]) == (True, 200)
    assert seen(client, sasha, denied["id"]) == (False, 404)

    allowed = publish(client, lesha, "Только Ане", visibility="allow", audience=["anya"])
    assert seen(client, anya, allowed["id"]) == (True, 200)
    assert seen(client, sasha, allowed["id"]) == (False, 404)

    outsider = client.post(
        "/api/recommendations",
        json={"name": "Чужой", "lat": 55.75, "lon": 37.6, "text": "нет", "visibility": "allow", "audience": ["stranger1"]},
        headers=lesha,
    )
    assert outsider.status_code == 422

    sasha_list = client.post("/api/lists", json={"title": "Сашино"}, headers=sasha).json()
    hidden = client.post(
        f"/api/lists/{sasha_list['id']}/places",
        json={"place_id": close["place"]["id"]},
        headers=sasha,
    )
    assert hidden.status_code == 404

    assert client.put("/api/friends/anya/close", json={"close": False}, headers=lesha).status_code == 204
    assert seen(client, anya, close["id"]) == (False, 404)
