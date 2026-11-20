"""Registration: login, password, nickname and an optional username."""

import re

from fastapi.testclient import TestClient

from app.main import app
from app.seed import DEMO_PASSWORD, reset_and_seed

PASSWORD = "Correct-horse1"


def client() -> TestClient:
    return TestClient(app)


def test_register_logs_in_and_rejects_duplicates() -> None:
    reset_and_seed()
    api = client()
    created = api.post(
        "/api/auth/register",
        json={"login": "new_user", "password": PASSWORD, "display_name": "Новый", "username": "new_user"},
    )
    assert created.status_code == 201
    token = created.json()["token"]
    me = api.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "new_user"
    assert me.json()["display_name"] == "Новый"

    again = api.post("/api/auth/login", json={"login": "new_user", "password": PASSWORD})
    assert again.status_code == 200

    duplicate_login = api.post(
        "/api/auth/register",
        json={"login": "new_user", "password": PASSWORD, "display_name": "Другой", "username": "other_name"},
    )
    assert duplicate_login.status_code == 409

    duplicate_username = api.post(
        "/api/auth/register",
        json={"login": "other_login", "password": PASSWORD, "display_name": "Другой", "username": "new_user"},
    )
    assert duplicate_username.status_code == 409


def test_empty_username_is_generated() -> None:
    reset_and_seed()
    api = client()
    created = api.post(
        "/api/auth/register",
        json={"login": "generated", "password": PASSWORD, "display_name": "Без ника"},
    )
    assert created.status_code == 201
    me = api.get("/api/me", headers={"Authorization": f"Bearer {created.json()['token']}"})
    assert re.fullmatch(r"user\d{8}", me.json()["username"])


def test_weak_password_and_bad_login_are_rejected() -> None:
    api = client()
    weak = api.post(
        "/api/auth/register",
        json={"login": "weak_user", "password": "demo1234", "display_name": "Слабый"},
    )
    assert weak.status_code == 422
    bad_login = api.post(
        "/api/auth/register",
        json={"login": "bad login", "password": PASSWORD, "display_name": "Плохой"},
    )
    assert bad_login.status_code == 422
    bad_name = api.post(
        "/api/auth/register",
        json={"login": "bad_name", "password": PASSWORD, "display_name": "<script>"},
    )
    assert bad_name.status_code == 422


def test_existing_seed_user_still_logs_in_with_demo_password() -> None:
    reset_and_seed()
    response = client().post("/api/auth/login", json={"login": "lesha", "password": DEMO_PASSWORD})
    assert response.status_code == 200
    assert "token" in response.json()
