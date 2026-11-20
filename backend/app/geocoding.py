import logging
import threading
import time
from dataclasses import asdict, dataclass

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import GeocodeCacheEntry

# Moscow including New Moscow, as Nominatim viewbox: left,top,right,bottom.
MOSCOW_VIEWBOX = "36.80,56.02,38.00,55.14"

logger = logging.getLogger("uvicorn.error")


class GeocoderUnavailable(Exception):
    pass


@dataclass(frozen=True)
class GeocodeResult:
    display_name: str
    lat: float
    lon: float
    city: str = ""


def city_from_address(address: object) -> str:
    if not isinstance(address, dict):
        return ""
    for key in ("city", "town", "village", "municipality"):
        value = address.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())[:120]
    return ""


def cache_has_city(results: list) -> bool:
    """Rows saved before city was stored have no city key and must be fetched again."""
    return bool(results) and all(isinstance(item, dict) and "city" in item for item in results)


def cached_result(item: dict) -> GeocodeResult:
    return GeocodeResult(
        display_name=item["display_name"],
        lat=float(item["lat"]),
        lon=float(item["lon"]),
        city=str(item.get("city") or ""),
    )


def normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


class NominatimGeocoder:
    """Public Nominatim allows at most 1 request per second per application, so every
    request in this process goes through one lock and results are cached in the database."""

    def __init__(
        self,
        url: str = settings.geocoder_url,
        user_agent: str = settings.geocoder_user_agent,
        min_interval_s: float = settings.geocoder_min_interval_s,
    ) -> None:
        self._url = url
        self._min_interval_s = min_interval_s
        self._client = httpx.Client(headers={"User-Agent": user_agent}, timeout=10.0)
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def fetch(self, query: str) -> list[GeocodeResult]:
        """Uncached request; callers are responsible for caching the results."""
        with self._lock:
            wait = self._min_interval_s - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            try:
                response = self._client.get(
                    self._url,
                    params={
                        "q": query,
                        "format": "jsonv2",
                        "limit": 5,
                        "countrycodes": "ru",
                        "accept-language": "ru",
                        "viewbox": MOSCOW_VIEWBOX,
                        "bounded": 1,
                        "addressdetails": 1,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Geocoder unavailable: %s: %r", type(exc).__name__, exc)
                raise GeocoderUnavailable(str(exc)) from exc
            finally:
                self._last_request_at = time.monotonic()
        return [
            GeocodeResult(
                display_name=item["display_name"],
                lat=float(item["lat"]),
                lon=float(item["lon"]),
                city=city_from_address(item.get("address")),
            )
            for item in response.json()
        ]

    def search(self, session: Session, query: str) -> tuple[list[GeocodeResult], bool]:
        """Returns results and whether they came from the cache."""
        key = normalize_query(query)
        cached = session.get(GeocodeCacheEntry, key)
        if cached is not None and cache_has_city(cached.results):
            return [cached_result(item) for item in cached.results], True
        results = self.fetch(query)
        session.merge(GeocodeCacheEntry(query=key, results=[asdict(r) for r in results]))
        session.commit()
        return results, False

    def _reverse_url(self) -> str:
        if self._url.endswith("/search"):
            return self._url[: -len("search")] + "reverse"
        return self._url.rstrip("/") + "/reverse"

    def fetch_reverse(self, lat: float, lon: float) -> GeocodeResult | None:
        with self._lock:
            wait = self._min_interval_s - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            try:
                response = self._client.get(
                    self._reverse_url(),
                    params={"lat": lat, "lon": lon, "format": "jsonv2", "accept-language": "ru", "addressdetails": 1},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Reverse geocoder unavailable: %s: %r", type(exc).__name__, exc)
                raise GeocoderUnavailable(str(exc)) from exc
            finally:
                self._last_request_at = time.monotonic()
        data = response.json()
        if not isinstance(data, dict) or "display_name" not in data:
            return None
        return GeocodeResult(
            display_name=data["display_name"],
            lat=float(data.get("lat", lat)),
            lon=float(data.get("lon", lon)),
            city=city_from_address(data.get("address")),
        )

    def reverse(self, session: Session, lat: float, lon: float) -> tuple[str, str, bool]:
        key = f"reverse:{lat:.5f},{lon:.5f}"
        cached = session.get(GeocodeCacheEntry, key)
        if cached is not None and (not cached.results or cache_has_city(cached.results)):
            item = cached.results[0] if cached.results else {}
            return item.get("display_name", ""), str(item.get("city") or ""), True
        result = self.fetch_reverse(lat, lon)
        address = result.display_name if result is not None else ""
        city = result.city if result is not None else ""
        session.merge(GeocodeCacheEntry(query=key, results=[asdict(result)] if result is not None else []))
        session.commit()
        return address, city, False


geocoder = NominatimGeocoder()
