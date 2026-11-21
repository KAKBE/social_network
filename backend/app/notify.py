"""PostgreSQL job queue for friend notifications.

The recommendation and the job are written in one transaction by the API.
A worker claims the job in a short transaction, then writes notifications only
if it still owns the lease. app.api imports enqueue from here, so the visibility
helper is imported inside recipient_ids, after api has finished loading.
"""

import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session

from app.models import FriendNotification, Friendship, NotificationJob, Recommendation


def lease_seconds() -> int:
    try:
        value = int(os.environ.get("NOTIFY_LEASE_SECONDS", "30"))
    except ValueError:
        value = 30
    return max(1, value)


def log(message: str) -> None:
    print(message, flush=True)


def enqueue(session: Session, recommendation: Recommendation) -> NotificationJob | None:
    """Add a job to the caller's transaction. A draft does not notify anyone."""
    if recommendation.status != "published":
        return None
    existing = session.scalar(
        select(NotificationJob).where(NotificationJob.recommendation_id == recommendation.id)
    )
    if existing is not None:
        return existing
    future = recommendation.publish_at is not None and recommendation.publish_at > datetime.now(UTC)
    job = NotificationJob(
        recommendation_id=recommendation.id,
        status="queued",
        available_at=recommendation.publish_at if future else datetime.now(UTC),
        attempts=0,
        process_count=0,
    )
    session.add(job)
    session.flush()
    if not future:
        session.execute(update(NotificationJob).where(NotificationJob.id == job.id).values(available_at=func.now()))
        session.refresh(job)
    return job


def claim_job(session: Session, worker_id: str) -> NotificationJob | None:
    """Claim one due job and commit before any notification is written."""
    now = func.now()
    job = session.scalar(
        select(NotificationJob)
        .where(
            NotificationJob.status.in_(("queued", "claimed")),
            NotificationJob.available_at <= now,
            or_(NotificationJob.lease_until.is_(None), NotificationJob.lease_until <= now),
        )
        .order_by(NotificationJob.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        session.rollback()
        return None
    token = str(uuid.uuid4())
    session.execute(
        text(
            """
            UPDATE notification_jobs
            SET status = 'claimed',
                claim_token = :token,
                claimed_by = :worker,
                attempts = attempts + 1,
                lease_until = now() + make_interval(secs => :lease)
            WHERE id = :id
            """
        ),
        {"token": token, "worker": worker_id, "lease": lease_seconds(), "id": job.id},
    )
    session.commit()
    session.refresh(job)
    log(
        f"job_id={job.id} event=claim claim_token={job.claim_token} "
        f"worker={worker_id} attempt={job.attempts}"
    )
    return job


def recipient_ids(session: Session, recommendation_id: int) -> list[int]:
    from app.api import recommendation_visible_to

    recommendation = session.get(Recommendation, recommendation_id)
    if recommendation is None:
        return []
    friends = session.scalars(
        select(Friendship.friend_id).where(Friendship.user_id == recommendation.author_id)
    ).all()
    visible: list[int] = []
    for friend_id in friends:
        row = session.scalar(
            select(Recommendation.id).where(
                Recommendation.id == recommendation_id,
                recommendation_visible_to(friend_id),
            )
        )
        if row is not None:
            visible.append(friend_id)
    return visible


def complete_job(session: Session, job_id: int, claim_token: str) -> str:
    """Write notifications only while this claim still owns the job."""
    job = session.scalar(select(NotificationJob).where(NotificationJob.id == job_id).with_for_update())
    if job is None:
        session.rollback()
        log(f"job_id={job_id} event=missing")
        return "missing"
    owns = session.scalar(
        select(NotificationJob.id).where(
            NotificationJob.id == job_id,
            NotificationJob.claim_token == claim_token,
            NotificationJob.status == "claimed",
            NotificationJob.lease_until > func.now(),
        )
    )
    if owns is None:
        session.rollback()
        log(f"job_id={job_id} event=stale_owner claim_token={claim_token}")
        return "stale_owner"
    recipients = recipient_ids(session, job.recommendation_id)
    for user_id in recipients:
        already = session.scalar(
            select(FriendNotification.id).where(
                FriendNotification.user_id == user_id,
                FriendNotification.recommendation_id == job.recommendation_id,
            )
        )
        if already is None:
            session.add(
                FriendNotification(
                    user_id=user_id,
                    recommendation_id=job.recommendation_id,
                    job_id=job.id,
                )
            )
    job.status = "done"
    job.process_count += 1
    job.finished_at = datetime.now(UTC)
    session.commit()
    log(f"job_id={job.id} event=done process_count={job.process_count} notifications={len(recipients)}")
    return "done"


def job_snapshot(session: Session, job_id: int) -> dict | None:
    job = session.get(NotificationJob, job_id)
    if job is None:
        return None
    notifications = session.scalar(
        select(func.count()).select_from(FriendNotification).where(FriendNotification.job_id == job.id)
    )
    return {
        "job_id": job.id,
        "recommendation_id": job.recommendation_id,
        "status": job.status,
        "claim_token": job.claim_token,
        "claimed_by": job.claimed_by,
        "attempts": job.attempts,
        "process_count": job.process_count,
        "notifications": int(notifications or 0),
    }
