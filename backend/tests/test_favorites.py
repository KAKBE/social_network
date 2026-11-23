"""Favorites keep a saved place after the author hides or deletes the post, and the owner can rename or remove a collection."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Place
from app.seed import DEMO_PASSWORD, reset_and_seed


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"login": username, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def publish(client: TestClient, headers: dict[str, str], name: str) -> dict:
    response = client.post(
        "/api/recommendations",
        json={"name": name, "address": "Москва", "lat": 55.75, "lon": 37.61, "text": name, "visibility": "friends"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def hide(client: TestClient, headers: dict[str, str], rec: dict) -> None:
    response = client.patch(
        f"/api/recommendations/{rec['id']}",
        json={"name": rec["place"]["name"], "text": rec["text"], "visibility": "self", "audience": []},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def test_owner_renames_and_deletes_a_collection_without_removing_the_place() -> None:
    reset_and_seed()
    client = TestClient(app)
    lesha = login(client, "lesha")
    anya = login(client, "anya")
    rec = publish(client, anya, "Булочная")
    created = client.post("/api/lists", json={"title": "Свидания"}, headers=lesha)
    assert created.status_code == 201, created.text
    list_id = created.json()["id"]
    saved = client.post(f"/api/lists/{list_id}/places", json={"place_id": rec["place"]["id"]}, headers=lesha)
    assert saved.status_code == 200, saved.text

    renamed = client.patch("/api/lists/" + str(list_id), json={"title": "  Вечер  "}, headers=lesha)
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Вечер"
    duplicate = client.patch("/api/lists/" + str(list_id), json={"title": "Учёба"}, headers=lesha)
    assert duplicate.status_code == 422
    assert duplicate.json()["detail"] == "Такое название уже есть"
    blank = client.patch("/api/lists/" + str(list_id), json={"title": "   "}, headers=lesha)
    assert blank.status_code == 422
    assert client.patch(f"/api/lists/{list_id}", json={"title": "Чужое"}, headers=anya).status_code == 404

    removed = client.delete(f"/api/lists/{list_id}", headers=lesha)
    assert removed.status_code == 204
    titles = {row["title"] for row in client.get("/api/lists", headers=lesha).json()}
    assert "Вечер" not in titles
    assert client.get(f"/api/recommendations/{rec['id']}", headers=anya).status_code == 200
    with SessionLocal() as session:
        assert session.get(Place, rec["place"]["id"]) is not None
        assert session.scalar(select(Place).where(Place.id == rec["place"]["id"])) is not None


def test_hidden_post_stays_in_favorites_and_the_author_still_opens_it() -> None:
    reset_and_seed()
    client = TestClient(app)
    anya = login(client, "anya")
    lesha = login(client, "lesha")
    rec = publish(client, anya, "Скрытая булочная")
    lesha_list = client.post("/api/lists", json={"title": "На потом"}, headers=lesha).json()
    anya_list = client.post("/api/lists", json={"title": "Своё"}, headers=anya).json()
    for headers, row in ((lesha, lesha_list), (anya, anya_list)):
        saved = client.post(f"/api/lists/{row['id']}/places", json={"place_id": rec["place"]["id"]}, headers=headers)
        assert saved.status_code == 200, saved.text

    hide(client, anya, rec)

    lesha_places = next(row["places"] for row in client.get("/api/lists", headers=lesha).json() if row["title"] == "На потом")
    kept = lesha_places[0]
    assert kept["limited"] is True
    assert kept["name"] == "Скрытая булочная"
    assert kept["address"] == "Москва"
    assert client.get(f"/api/recommendations/{rec['id']}", headers=lesha).status_code == 404

    anya_places = next(row["places"] for row in client.get("/api/lists", headers=anya).json() if row["title"] == "Своё")
    assert anya_places[0]["limited"] is False
    assert client.get(f"/api/recommendations/{rec['id']}", headers=anya).status_code == 200

    deleted = client.delete(f"/api/recommendations/{rec['id']}", headers=anya)
    assert deleted.status_code == 204
    after = next(row["places"] for row in client.get("/api/lists", headers=lesha).json() if row["title"] == "На потом")
    assert after[0]["limited"] is True
    assert after[0]["name"] == "Скрытая булочная"
    assert after[0]["id"] is None
