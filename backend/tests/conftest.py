import os
import sys
import tempfile

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://posledu:posledu@localhost:5432/posledu_test")
os.environ.setdefault("UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "posledu-test-uploads"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Imported after DATABASE_URL and sys.path are set: app.db reads the URL at import time.
from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402
from app.migrations import upgrade_to_head  # noqa: E402


def pytest_configure(config):
    # app.seed resets whatever database the URL names. Pytest must not be that reset for the demo database.
    with engine.connect() as connection:
        name = connection.execute(text("select current_database()")).scalar()
    if not str(name).endswith("_test"):
        raise RuntimeError(f"pytest подключён к базе {name}. Для тестов нужна база с именем на _test")
    # app.main refuses to start on an outdated schema, so migrate before test modules import it.
    upgrade_to_head()
