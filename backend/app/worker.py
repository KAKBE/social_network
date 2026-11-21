"""Separate process that claims notification jobs and writes the result after commit."""

import argparse
import json
import os
import socket
import time

from app.db import SessionLocal
from app.notify import claim_job, complete_job, job_snapshot, log


def process_one(worker_id: str, *, crash: bool, hold: float) -> int:
    with SessionLocal() as session:
        job = claim_job(session, worker_id)
    if job is None:
        log("event=idle")
        return 0
    if crash:
        log(f"job_id={job.id} event=crash-after-claim")
        return 0
    if hold > 0:
        log(f"job_id={job.id} event=hold seconds={hold}")
        time.sleep(hold)
    with SessionLocal() as session:
        result = complete_job(session, job.id, job.claim_token or "")
    return 0 if result == "done" else 2


def show_status(job_id: int) -> int:
    with SessionLocal() as session:
        snapshot = job_snapshot(session, job_id)
    if snapshot is None:
        log(f"job_id={job_id} event=missing")
        return 1
    log(json.dumps(snapshot, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Воркер уведомлений о новых рекомендациях")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--crash-after-claim", action="store_true")
    parser.add_argument("--hold-after-claim", type=float, default=0)
    parser.add_argument("--status", type=int)
    parser.add_argument("--worker", default=f"{socket.gethostname()}-{os.getpid()}")
    args = parser.parse_args(argv)
    if args.status is not None:
        return show_status(args.status)
    if args.once or args.crash_after_claim or args.hold_after_claim:
        return process_one(args.worker, crash=args.crash_after_claim, hold=args.hold_after_claim)
    while True:
        process_one(args.worker, crash=False, hold=0)
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
