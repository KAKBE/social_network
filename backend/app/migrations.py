"""Schema version control through Alembic: the schema changes only via files in backend/migrations/versions."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.db import engine

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    # Keep the host application's logging setup (uvicorn, pytest) instead of alembic.ini's.
    config.attributes["configure_logger"] = False
    return config


def upgrade_to_head() -> None:
    command.upgrade(alembic_config(), "head")


def assert_schema_current() -> None:
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    if current != head:
        raise RuntimeError(
            f"Database schema is at revision {current}, expected {head}. "
            "Run `alembic upgrade head` in backend/ before starting the app."
        )
