"""An author can add a category on their profile and assign posts to it."""

from fastapi.testclient import TestClient

from app.main import app
from app.seed import DEMO_PASSWORD, reset_and_seed


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"login": username, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_custom_category_stays_on_the_profile_and_can_be_renamed() -> None:
    reset_and_seed()
    client = TestClient(app)
    lesha = login(client, "lesha")
    anya = login(client, "anya")

    created = client.post("/api/me/categories", json={"title": "  Кофе  "}, headers=lesha)
    assert created.status_code == 201, created.text
    assert created.json()["title"] == "Кофе"
    duplicate = client.post("/api/me/categories", json={"title": "кофе"}, headers=lesha)
    assert duplicate.status_code == 422
    assert duplicate.json()["detail"] == "Такая категория уже есть"
    reserved = client.post("/api/me/categories", json={"title": "Учёба"}, headers=lesha)
    assert reserved.status_code == 422
    blank = client.post("/api/me/categories", json={"title": "   "}, headers=lesha)
    assert blank.status_code == 422

    published = client.post(
        "/api/recommendations",
        json={
            "name": "Кофейня",
            "address": "Москва",
            "lat": 55.75,
            "lon": 37.61,
            "text": "Тихо",
            "visibility": "friends",
            "category": "Кофе",
        },
        headers=lesha,
    )
    assert published.status_code == 201, published.text
    assert published.json()["category"] == "Кофе"
    stolen = client.post(
        "/api/recommendations",
        json={
            "name": "Чужое",
            "address": "Москва",
            "lat": 55.76,
            "lon": 37.62,
            "text": "Нет",
            "visibility": "friends",
            "category": "Кофе",
        },
        headers=anya,
    )
    assert stolen.status_code == 422

    lesha_id = client.get("/api/me", headers=lesha).json()["public_id"]
    visible = client.get(f"/api/users/{lesha_id}/recommendations", params={"category": "Кофе"}, headers=anya)
    assert visible.status_code == 200
    assert [item["place"]["name"] for item in visible.json()] == ["Кофейня"]

    renamed = client.patch("/api/me/categories/Кофе", json={"title": "Чай"}, headers=lesha)
    assert renamed.status_code == 200, renamed.text
    moved = client.get(f"/api/users/{lesha_id}/recommendations", params={"category": "Чай"}, headers=lesha)
    assert moved.status_code == 200
    assert moved.json()[0]["category"] == "Чай"

    removed = client.delete("/api/me/categories/Чай", headers=lesha)
    assert removed.status_code == 204
    kept = client.get(f"/api/recommendations/{published.json()['id']}", headers=lesha)
    assert kept.status_code == 200
    assert kept.json()["category"] == ""
    assert client.get("/api/me/categories", headers=lesha).json() == []


def test_custom_category_rejects_reserved_long_and_extra_titles() -> None:
    reset_and_seed()
    client = TestClient(app)
    lesha = login(client, "lesha")

    reserved = client.post("/api/me/categories", json={"title": "STUDY"}, headers=lesha)
    assert reserved.status_code == 422
    assert reserved.json()["detail"] == "Это название уже занято"
    too_long = client.post("/api/me/categories", json={"title": "я" * 25}, headers=lesha)
    assert too_long.status_code == 422
    assert "Некорректное название категории" in too_long.text
    blocked = client.post("/api/me/categories", json={"title": "all"}, headers=lesha)
    assert blocked.status_code == 422
    assert "Некорректное название категории" in blocked.text

    for index in range(1, 13):
        created = client.post("/api/me/categories", json={"title": f"К{index}"}, headers=lesha)
        assert created.status_code == 201, created.text
    extra = client.post("/api/me/categories", json={"title": "К13"}, headers=lesha)
    assert extra.status_code == 422
    assert extra.json()["detail"] == "Категорий уже достаточно"

    renamed = client.patch("/api/me/categories/К1", json={"title": "к1"}, headers=lesha)
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "к1"
