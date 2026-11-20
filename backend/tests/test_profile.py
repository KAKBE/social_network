"""Profile editing, password change, theme and one profile photo."""

import base64
import io
import struct

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Friendship, User
from app.seed import reset_and_seed

PASSWORD = "Correct-horse1"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def api() -> TestClient:
    return TestClient(app)


def register(client: TestClient, login: str) -> dict[str, str]:
    created = client.post(
        "/api/auth/register",
        json={"login": login, "password": PASSWORD, "display_name": login, "username": login},
    )
    assert created.status_code == 201, created.text
    return {"Authorization": f"Bearer {created.json()['token']}"}


def befriend(login_a: str, login_b: str) -> None:
    with SessionLocal() as session:
        a = session.scalar(select(User).where(User.login == login_a))
        b = session.scalar(select(User).where(User.login == login_b))
        session.add(Friendship(user_id=a.id, friend_id=b.id))
        session.add(Friendship(user_id=b.id, friend_id=a.id))
        session.commit()


def png_size(width: int, height: int) -> bytes:
    signature = bytes.fromhex("89504e470d0a1a0a")
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return signature + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00\x00\x00\x00"


def test_profile_fields_theme_and_username_conflict() -> None:
    reset_and_seed()
    client = api()
    headers = register(client, "profile_owner")
    updated = client.patch(
        "/api/me",
        headers=headers,
        json={
            "display_name": "Владелец",
            "username": "owner_name",
            "bio": "Люблю тихие места",
            "profile_visibility": "friends",
            "theme": "light",
        },
    )
    assert updated.status_code == 200
    me = client.get("/api/me", headers=headers).json()
    assert me["display_name"] == "Владелец"
    assert me["username"] == "owner_name"
    assert me["bio"] == "Люблю тихие места"
    assert me["profile_visibility"] == "friends"
    assert me["theme"] == "light"
    assert me["login"] == "profile_owner"

    register(client, "taken_name")
    conflict = client.patch("/api/me", headers=headers, json={"username": "taken_name"})
    assert conflict.status_code == 409
    bad = client.patch("/api/me", headers=headers, json={"display_name": "<b>"})
    assert bad.status_code == 422
    bad_theme = client.patch("/api/me", headers=headers, json={"theme": "blue"})
    assert bad_theme.status_code == 422


def test_password_change_needs_current_and_matching_repeat() -> None:
    reset_and_seed()
    client = api()
    headers = register(client, "password_user")
    mismatch = client.post(
        "/api/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "password": "New-password1", "password_repeat": "Other-password1"},
    )
    assert mismatch.status_code == 422
    weak = client.post(
        "/api/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "password": "abcdefghijkl", "password_repeat": "abcdefghijkl"},
    )
    assert weak.status_code == 422
    wrong = client.post(
        "/api/me/password",
        headers=headers,
        json={"current_password": "Wrong-password1", "password": "New-password1", "password_repeat": "New-password1"},
    )
    assert wrong.status_code == 401

    changed = client.post(
        "/api/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "password": "New-password1", "password_repeat": "New-password1"},
    )
    assert changed.status_code == 204
    assert client.post("/api/auth/login", json={"login": "password_user", "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"login": "password_user", "password": "New-password1"}).status_code == 200


def test_avatar_is_one_checked_image_and_hidden_with_profile() -> None:
    reset_and_seed()
    client = api()
    owner = register(client, "avatar_owner")
    stranger = register(client, "avatar_guest")
    client.patch("/api/me", headers=owner, json={"bio": "Секрет", "profile_visibility": "friends"})

    rejected = client.post(
        "/api/me/avatar",
        headers=owner,
        files={"file": ("photo.gif", io.BytesIO(b"GIF89a"), "image/gif")},
    )
    assert rejected.status_code == 422
    huge = client.post(
        "/api/me/avatar",
        headers=owner,
        files={"file": ("big.png", io.BytesIO(png_size(5000, 5000)), "image/png")},
    )
    assert huge.status_code == 422

    saved = client.post(
        "/api/me/avatar",
        headers=owner,
        files={"file": ("face.png", io.BytesIO(PNG_1X1), "image/png")},
    )
    assert saved.status_code == 200
    assert client.get("/api/me", headers=owner).json()["has_avatar"] is True
    own = client.get("/api/me/avatar", headers=owner)
    assert own.status_code == 200
    assert own.headers["content-type"].startswith("image/png")
    assert own.content == PNG_1X1

    public_id = client.get("/api/me", headers=owner).json()["public_id"]
    hidden = client.get(f"/api/users/{public_id}", headers=stranger)
    assert hidden.status_code == 200
    assert hidden.json()["bio"] == ""
    assert hidden.json()["has_avatar"] is False
    assert client.get(f"/api/users/{public_id}/avatar", headers=stranger).status_code == 404

    befriend("avatar_owner", "avatar_guest")
    visible = client.get(f"/api/users/{public_id}", headers=stranger).json()
    assert visible["bio"] == "Секрет"
    assert visible["has_avatar"] is True
    assert client.get(f"/api/users/{public_id}/avatar", headers=stranger).content == PNG_1X1
