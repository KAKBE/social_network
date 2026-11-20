"""Username search and friend requests. Friendship starts only after acceptance."""

from fastapi.testclient import TestClient

from app.main import app
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


def test_search_and_friend_request_until_accept() -> None:
    reset_and_seed()
    client = api()
    owner = register(client, "friend_owner")
    guest = register(client, "friend_guest")
    client.patch("/api/me", headers=owner, json={"bio": "Только друзьям", "profile_visibility": "friends"})
    owner_id = client.get("/api/me", headers=owner).json()["public_id"]

    found = client.get("/api/users/search", params={"q": "friend_ow"}, headers=guest)
    assert found.status_code == 200
    assert [item["username"] for item in found.json()] == ["friend_owner"]
    assert found.json()[0]["relation"] == "none"
    assert client.get("/api/users/search", params={"q": "friend_"}, headers=owner).json()[0]["username"] == "friend_guest"

    sent = client.post("/api/friend-requests", headers=guest, json={"username": "friend_owner"})
    assert sent.status_code == 201
    request_id = sent.json()["id"]
    assert client.get(f"/api/users/{owner_id}", headers=guest).json()["bio"] == ""
    again = client.post("/api/friend-requests", headers=guest, json={"username": "friend_owner"})
    assert again.status_code == 409
    self_request = client.post("/api/friend-requests", headers=guest, json={"username": "friend_guest"})
    assert self_request.status_code == 409

    incoming = client.get("/api/friend-requests", headers=owner).json()
    assert [item["id"] for item in incoming] == [request_id]
    assert incoming[0]["username"] == "friend_guest"

    rejected = client.post(f"/api/friend-requests/{request_id}/reject", headers=guest)
    assert rejected.status_code == 403
    assert client.post(f"/api/friend-requests/{request_id}/reject", headers=owner).status_code == 204
    assert client.get(f"/api/users/{owner_id}", headers=guest).json()["bio"] == ""

    sent = client.post("/api/friend-requests", headers=guest, json={"username": "friend_owner"})
    request_id = sent.json()["id"]
    assert client.post(f"/api/friend-requests/{request_id}/accept", headers=owner).status_code == 204
    assert client.get(f"/api/users/{owner_id}", headers=guest).json()["bio"] == "Только друзьям"
    assert client.get("/api/users/search", params={"q": "friend_owner"}, headers=guest).json()[0]["relation"] == "friend"
