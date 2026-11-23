"""The notification worker keeps running and Compose starts it with the database."""

from pathlib import Path

from app.worker import public_error, serve

ROOT = Path(__file__).resolve().parents[2]


def test_serve_retries_without_printing_the_database_password(monkeypatch, capsys) -> None:
    calls = {"n": 0}

    def fail_once(worker_id: str, *, crash: bool, hold: float, log_idle: bool = True) -> int:
        calls["n"] += 1
        calls["log_idle"] = log_idle
        if calls["n"] == 1:
            raise RuntimeError("password=posledu postgresql+psycopg://posledu:posledu@db:5432/posledu")
        return 0

    monkeypatch.setattr("app.worker.process_one", fail_once)
    monkeypatch.setattr("app.worker.time.sleep", lambda _seconds: None)
    serve("retry", pause_s=0, cycles=2)
    printed = capsys.readouterr().out
    assert calls["n"] == 2
    assert calls["log_idle"] is False
    assert "event=retry" in printed
    assert "event=idle" not in printed
    assert "posledu:posledu" not in printed
    assert "password=posledu" not in printed


def test_public_error_hides_the_connection_url() -> None:
    text = public_error(RuntimeError("failed postgresql+psycopg://posledu:secret@db:5432/posledu"))
    assert "secret" not in text
    assert "postgresql://***" in text


def test_compose_starts_the_worker_with_the_database() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "worker:" in compose
    assert "postgresql+psycopg://posledu:posledu@db:5432/posledu" in compose
    assert "unless-stopped" in compose
    assert "app.worker" in (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
