"""A draft or a future recommendation is visible only to its author."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.geocoding import GeocodeResult, geocoder
from app.main import app
from app.models import GeocodeCacheEntry
from app.seed import DEMO_PASSWORD, reset_and_seed


def api() -> TestClient:
    return TestClient(app)


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"login": username, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def ids(client: TestClient, headers: dict[str, str]) -> set[int]:
    feed = client.get("/api/feed", params={"limit": 200}, headers=headers)
    assert feed.status_code == 200, feed.text
    return {item["id"] for item in feed.json()}


def test_draft_schedule_list_and_reverse(monkeypatch) -> None:
    reset_and_seed()
    client = api()
    lesha = login(client, "lesha")
    anya = login(client, "anya")

    draft = client.post(
        "/api/recommendations",
        json={"name": "Черновик", "lat": 55.75, "lon": 37.6, "text": "Черновик", "draft": True},
        headers=lesha,
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]
    assert draft_id in ids(client, lesha)
    assert draft_id not in ids(client, anya)
    assert client.get(f"/api/recommendations/{draft_id}", headers=anya).status_code == 404

    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    scheduled = client.post(
        "/api/recommendations",
        json={"name": "Позже", "lat": 55.76, "lon": 37.61, "text": "Позже", "publish_at": future},
        headers=lesha,
    )
    assert scheduled.status_code == 201, scheduled.text
    assert scheduled.json()["id"] not in ids(client, anya)
    assert scheduled.json()["id"] in ids(client, lesha)

    both = client.post(
        "/api/recommendations",
        json={"name": "Оба", "lat": 55.7, "lon": 37.6, "text": "Оба", "draft": True, "publish_at": future},
        headers=lesha,
    )
    assert both.status_code == 422

    study = next(item for item in client.get("/api/lists", headers=lesha).json() if item["title"] == "Учёба")
    saved = client.post(
        "/api/recommendations",
        json={"name": "В список", "lat": 55.74, "lon": 37.62, "text": "В список", "list_id": study["id"]},
        headers=lesha,
    )
    assert saved.status_code == 201, saved.text
    again = client.get("/api/lists", headers=lesha).json()
    study = next(item for item in again if item["title"] == "Учёба")
    assert saved.json()["place"]["id"] in {place["id"] for place in study["places"]}

    foreign = client.post("/api/lists", json={"title": "Чужой"}, headers=anya).json()
    denied = client.post(
        "/api/recommendations",
        json={"name": "Чужой список", "lat": 55.7, "lon": 37.6, "text": "нет", "list_id": foreign["id"]},
        headers=lesha,
    )
    assert denied.status_code == 404
    assert "Чужой список" not in {item["place"]["name"] for item in client.get("/api/feed", headers=lesha).json()}

    def fake_reverse(lat: float, lon: float) -> GeocodeResult:
        return GeocodeResult(display_name="Москва, точка", lat=lat, lon=lon)

    monkeypatch.setattr(geocoder, "fetch_reverse", fake_reverse)
    with SessionLocal() as session:
        cached = session.get(GeocodeCacheEntry, "reverse:55.75100,37.61800")
        if cached is not None:
            session.delete(cached)
            session.commit()
    first = client.post("/api/geocode/reverse", json={"lat": 55.751, "lon": 37.618}, headers=lesha)
    assert first.status_code == 200, first.text
    assert first.json()["address"] == "Москва, точка"
    assert first.json()["cached"] is False
    second = client.post("/api/geocode/reverse", json={"lat": 55.751, "lon": 37.618}, headers=lesha)
    assert second.json()["cached"] is True


def test_author_can_publish_a_draft() -> None:
    reset_and_seed()
    client = api()
    lesha = login(client, "lesha")
    anya = login(client, "anya")
    draft = client.post(
        "/api/recommendations",
        json={"name": "Позже", "lat": 55.75, "lon": 37.61, "text": "Сначала черновик", "draft": True},
        headers=lesha,
    )
    assert draft.status_code == 201, draft.text
    rec_id = draft.json()["id"]
    hidden = client.post(f"/api/recommendations/{rec_id}/publish", headers=anya)
    assert hidden.status_code == 404
    published = client.post(f"/api/recommendations/{rec_id}/publish", headers=lesha)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert rec_id in ids(client, anya)
    again = client.post(f"/api/recommendations/{rec_id}/publish", headers=lesha)
    assert again.status_code == 422


def test_geocode_cache_without_city_is_refetched(monkeypatch) -> None:
    reset_and_seed()
    client = api()
    lesha = login(client, "lesha")
    with SessionLocal() as session:
        session.merge(
            GeocodeCacheEntry(query="москва точка", results=[{"display_name": "старый", "lat": 55.7, "lon": 37.6}])
        )
        session.commit()

    def fake_fetch(query: str) -> list[GeocodeResult]:
        return [GeocodeResult(display_name="Москва, новая", lat=55.75, lon=37.62, city="Москва")]

    monkeypatch.setattr(geocoder, "fetch", fake_fetch)
    response = client.post("/api/geocode", json={"query": "Москва точка"}, headers=lesha)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cached"] is False
    assert body["results"][0]["city"] == "Москва"
