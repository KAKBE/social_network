"""ADR-4 metric: the place records whether its author corrected the geocoder's point on the map."""

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Place, Recommendation
from app.seed import DEMO_PASSWORD, reset_and_seed


def test_point_corrected_is_stored_and_defaults_to_false() -> None:
    reset_and_seed()
    client = TestClient(app)
    token = client.post("/api/auth/login", json={"username": "lesha", "password": DEMO_PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    body = {"name": "Место", "address": "Москва", "lat": 55.75, "lon": 37.6, "text": "Проверка"}

    corrected = client.post("/api/recommendations", json=body | {"point_corrected": True}, headers=headers)
    default = client.post("/api/recommendations", json=body, headers=headers)
    assert corrected.status_code == default.status_code == 201

    with SessionLocal() as session:
        stored = {
            rec_id: session.get(Place, session.get(Recommendation, rec_id).place_id).point_corrected
            for rec_id in (corrected.json()["id"], default.json()["id"])
        }
    assert stored == {corrected.json()["id"]: True, default.json()["id"]: False}
