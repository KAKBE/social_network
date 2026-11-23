"""Friend notifications are a PostgreSQL job, completed by a separate worker."""

import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.db import SessionLocal
from app.main import app
from app.models import FriendNotification, Friendship, NotificationJob, Place, Recommendation, User
from app.notify import enqueue
from app.seed import DEMO_PASSWORD, reset_and_seed

BACKEND = Path(__file__).resolve().parents[1]


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"login": username, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def publish(client: TestClient, headers: dict[str, str], name: str, **extra) -> dict:
    response = client.post(
        "/api/recommendations",
        json={"name": name, "lat": 55.75, "lon": 37.62, "text": name, **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def job_for(recommendation_id: int) -> dict | None:
    with SessionLocal() as session:
        job = session.scalar(select(NotificationJob).where(NotificationJob.recommendation_id == recommendation_id))
        if job is None:
            return None
        return {
            "id": job.id,
            "status": job.status,
            "attempts": job.attempts,
            "process_count": job.process_count,
            "claim_token": job.claim_token,
        }


def run_worker(*args: str, timeout: float = 20) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["NOTIFY_LEASE_SECONDS"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "app.worker", *args],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def test_friend_notification_job_survives_claim_loss(monkeypatch) -> None:
    monkeypatch.setenv("NOTIFY_LEASE_SECONDS", "1")
    with SessionLocal() as session:
        database = session.execute(text("select current_database()")).scalar()
    assert str(database).endswith("_test")
    reset_and_seed()
    client = TestClient(app)
    lesha = login(client, "lesha")
    anya = login(client, "anya")
    stranger = login(client, "stranger1")

    draft = publish(client, lesha, "Черновик", draft=True)
    assert job_for(draft["id"]) is None

    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    scheduled = publish(client, lesha, "Позже", publish_at=future)
    waiting = run_worker("--once", "--worker", "early")
    assert "event=idle" in waiting.stdout
    assert job_for(scheduled["id"])["status"] == "queued"

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.username == "lesha"))
        place = Place(name="Откат", address="", lat=1, lon=1, created_by=user.id, city="")
        session.add(place)
        session.flush()
        rec = Recommendation(author_id=user.id, place_id=place.id, text="Откат", status="published")
        session.add(rec)
        session.flush()
        enqueue(session, rec)
        rolled_back = rec.id
        session.rollback()
    assert job_for(rolled_back) is None

    created = publish(client, lesha, "Сразу")
    normal = run_worker("--once", "--worker", "normal")
    assert "event=done" in normal.stdout
    assert "process_count=1" in normal.stdout
    with SessionLocal() as session:
        author = session.scalar(select(User).where(User.username == "lesha"))
        friends = session.scalar(select(func.count()).select_from(Friendship).where(Friendship.user_id == author.id))
        done = job_for(created["id"])
        assert done["status"] == "done"
        assert done["process_count"] == 1
        assert f"notifications={friends}" in normal.stdout
    notes = client.get("/api/notifications", headers=anya).json()
    assert notes["unread"] == 1
    assert notes["items"][0]["place_name"] == "Сразу"
    assert client.get("/api/notifications", headers=stranger).json()["unread"] == 0
    assert client.get("/api/notifications", headers=lesha).json()["unread"] == 0
    read = client.post(f"/api/notifications/{notes['items'][0]['id']}/read", headers=anya)
    assert read.status_code == 200, read.text
    assert read.json()["unread"] == 0

    client.put("/api/friends/anya/close", json={"close": True}, headers=lesha)
    close = publish(client, lesha, "Близким", visibility="close")
    close_run = run_worker("--once", "--worker", "close")
    assert "notifications=1" in close_run.stdout
    close_notes = client.get("/api/notifications", headers=anya).json()
    assert any(item["place_name"] == "Близким" for item in close_notes["items"])
    sasha = login(client, "sasha")
    assert all(item["place_name"] != "Близким" for item in client.get("/api/notifications", headers=sasha).json()["items"])

    crashed_rec = publish(client, lesha, "После сбоя")
    crashed_job = job_for(crashed_rec["id"])
    # Ожидание: тот же job_id будет взят повторно после аренды и завершён без новой постановки.
    crash = run_worker("--crash-after-claim", "--worker", "crash")
    assert crash.returncode == 0, crash.stdout + crash.stderr
    assert f"job_id={crashed_job['id']} event=claim" in crash.stdout
    assert f"job_id={crashed_job['id']} event=crash-after-claim" in crash.stdout
    assert job_for(crashed_rec["id"])["status"] == "claimed"
    time.sleep(1.2)
    recovered = run_worker("--once", "--worker", "recover")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert f"job_id={crashed_job['id']} event=claim" in recovered.stdout
    assert f"job_id={crashed_job['id']} event=done process_count=1" in recovered.stdout
    recovered_job = job_for(crashed_rec["id"])
    assert recovered_job["id"] == crashed_job["id"]
    assert recovered_job["attempts"] == 2
    assert recovered_job["process_count"] == 1
    assert recovered_job["claim_token"] != crash.stdout.split("claim_token=")[1].split()[0]

    stale_rec = publish(client, lesha, "Старый владелец")
    stale_job = job_for(stale_rec["id"])
    # Ожидание: первый воркер опоздает, второй завершит задание, запись первого будет отклонена.
    env = os.environ.copy()
    env["NOTIFY_LEASE_SECONDS"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    holder = subprocess.Popen(
        [sys.executable, "-m", "app.worker", "--hold-after-claim", "3", "--worker", "holder"],
        cwd=BACKEND,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    claim_line = holder.stdout.readline()
    hold_line = holder.stdout.readline()
    time.sleep(1.2)
    finisher = run_worker("--once", "--worker", "finisher")
    holder_out, _ = holder.communicate(timeout=10)
    assert holder.returncode == 2, claim_line + hold_line + holder_out
    assert f"job_id={stale_job['id']}" in claim_line
    assert f"job_id={stale_job['id']} event=stale_owner" in holder_out
    assert f"job_id={stale_job['id']} event=done process_count=1" in finisher.stdout
    finished = job_for(stale_rec["id"])
    assert finished["process_count"] == 1
    assert finished["status"] == "done"
    with SessionLocal() as session:
        author = session.scalar(select(User).where(User.username == "lesha"))
        friends = session.scalar(select(func.count()).select_from(Friendship).where(Friendship.user_id == author.id))
        stored = session.scalar(
            select(func.count())
            .select_from(FriendNotification)
            .where(FriendNotification.recommendation_id == stale_rec["id"])
        )
    assert stored == friends
    status = run_worker("--status", str(finished["id"]))
    assert status.returncode == 0, status.stdout + status.stderr
    assert '"process_count": 1' in status.stdout
