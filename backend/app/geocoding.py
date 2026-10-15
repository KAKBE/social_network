import threading
import time
from dataclasses import asdict, dataclass

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import GeocodeCacheEntry

# Moscow including New Moscow, as Nominatim viewbox: left,top,right,bottom.
MOSCOW_VIEWBOX = "36.80,56.02,38.00,55.14"


class GeocoderUnavailable(Exception):
    pass


@dataclass(frozen=True)
class GeocodeResult:
    display_name: str
    lat: float
    lon: float


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

    def _fetch(self, query: str) -> list[GeocodeResult]:
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
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise GeocoderUnavailable(str(exc)) from exc
            finally:
                self._last_request_at = time.monotonic()
        return [
            GeocodeResult(display_name=item["display_name"], lat=float(item["lat"]), lon=float(item["lon"]))
            for item in response.json()
        ]

    def search(self, session: Session, query: str) -> tuple[list[GeocodeResult], bool]:
        """Returns results and whether they came from the cache."""
        key = normalize_query(query)
        cached = session.get(GeocodeCacheEntry, key)
        if cached is not None:
            return [GeocodeResult(**item) for item in cached.results], True
        results = self._fetch(query)
        session.merge(GeocodeCacheEntry(query=key, results=[asdict(r) for r in results]))
        session.commit()
        return results, False


geocoder = NominatimGeocoder()
