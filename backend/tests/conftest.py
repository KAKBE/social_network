import os
import sys

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://posledu:posledu@localhost:5432/posledu_test")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
