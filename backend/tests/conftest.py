import os
import sys
import tempfile

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://posledu:posledu@localhost:5432/posledu_test")
os.environ.setdefault("UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "posledu-test-uploads"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Imported after DATABASE_URL and sys.path are set: app.db reads the URL at import time.
from app.migrations import upgrade_to_head  # noqa: E402


def pytest_configure(config):
    # app.main refuses to start on an outdated schema, so migrate before test modules import it.
    upgrade_to_head()
