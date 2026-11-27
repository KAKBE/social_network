"""Accepting a request tells the sender. Rejecting one does not."""

from fastapi.testclient import TestClient

from app.main import app
from app.seed import reset_and_seed

PASSWORD = "Correct-horse1"


def api() -> TestClient:
    return TestClient(app)


def register(client: TestClient, login: str, display_name: str) -> dict[str, str]:
    created = client.post(
        "/api/auth/register",
        json={"login": login, "password": PASSWORD, "display_name": display_name, "username": login},
    )
    assert created.status_code == 201, created.text
    return {"Authorization": f"Bearer {created.json()['token']}"}


def test_accept_notifies_the_sender_and_reject_stays_quiet() -> None:
    reset_and_seed()
    client = api()
    owner = register(client, "reply_owner", "Лёша")
    guest = register(client, "reply_guest", "Таня")
    stranger = register(client, "reply_stranger", "Марк")
    renamed = client.patch("/api/me", headers=owner, json={"surname": "Волков"})
    assert renamed.status_code == 200

    sent = client.post("/api/friend-requests", headers=guest, json={"username": "reply_owner"})
    assert sent.status_code == 201
    request_id = sent.json()["id"]
    assert client.post(f"/api/friend-requests/{request_id}/reject", headers=owner).status_code == 204
    assert client.get("/api/friend-replies", headers=guest).json() == []
    assert client.get("/api/friend-replies", headers=owner).json() == []

    sent = client.post("/api/friend-requests", headers=guest, json={"username": "reply_owner"})
    request_id = sent.json()["id"]
    assert client.post(f"/api/friend-requests/{request_id}/accept", headers=owner).status_code == 204

    guest_notes = client.get("/api/friend-replies", headers=guest).json()
    assert len(guest_notes) == 1
    assert guest_notes[0]["username"] == "reply_owner"
    assert guest_notes[0]["display_name"] == "Лёша"
    assert guest_notes[0]["surname"] == "Волков"
    assert client.get("/api/friend-replies", headers=owner).json() == []
    assert client.get("/api/notifications", headers=guest).json()["unread"] == 0

    hidden = client.post(f"/api/friend-replies/{guest_notes[0]['id']}/read", headers=stranger)
    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "Уведомление не найдено"
    missing = client.post("/api/friend-replies/999999/read", headers=guest)
    assert missing.status_code == 404

    read = client.post(f"/api/friend-replies/{guest_notes[0]['id']}/read", headers=guest)
    assert read.status_code == 200
    assert read.json() == []
    again = client.post(f"/api/friend-replies/{guest_notes[0]['id']}/read", headers=guest)
    assert again.status_code == 200
    assert again.json() == []
    assert client.get("/api/friend-replies", headers=guest).json() == []
