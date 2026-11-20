import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    tile_url: str
    tile_attribution: str
    geocoder_url: str
    geocoder_user_agent: str
    geocoder_min_interval_s: float
    frontend_dist: str
    upload_dir: str


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://posledu:posledu@localhost:5432/posledu",
        ),
        # Tile and geocoder endpoints are configuration, not code: the OSM policies require
        # that the provider can be switched without a software update.
        tile_url=os.getenv("TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"),
        tile_attribution=os.getenv(
            "TILE_ATTRIBUTION",
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        ),
        geocoder_url=os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org/search"),
        geocoder_user_agent=os.getenv(
            "GEOCODER_USER_AGENT",
            "PoSledu-PoC/0.1 (student project HSE MIEM; contact: aaveretnov@edu.hse.ru)",
        ),
        geocoder_min_interval_s=float(os.getenv("GEOCODER_MIN_INTERVAL_S", "1.0")),
        frontend_dist=os.getenv(
            "FRONTEND_DIST",
            os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"),
        ),
        upload_dir=os.getenv(
            "UPLOAD_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "uploads"),
        ),
    )


settings = load_settings()
