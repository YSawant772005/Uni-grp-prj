"""In-process background worker for ingestion/refresh jobs (APScheduler; no Redis).

Jobs are idempotent and bounded: a queued job is claimed atomically (``FOR UPDATE
SKIP LOCKED``), validated, then finished with an honest status. The MVP does not
fetch external documents — a ``refresh`` job therefore validates the source
registry entry, records zero-record counters and finishes ``partial`` with a
sanitized ``error_summary`` explaining that no content fetch occurred. It never
marks facts verified and never auto-publishes a candidate (rules.md §40, §43).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import IngestionJob, Source

logger = logging.getLogger("uni.api")

WORKER_VERSION = "mvp-worker-1"
POLL_SECONDS = 15
BATCH_SIZE = 5
NO_FETCH_REASON = ("content fetch not enabled in MVP; validated source registry entry "
                   "only; no candidate facts were created or published")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _process_job(db, job: IngestionJob) -> None:
    """Validate a claimed refresh job. Never fabricates records or verifications."""
    source = db.get(Source, job.source_id) if job.source_id else None
    if source is None:
        job.status = "failed"
        job.error_summary = "source no longer exists"
        return
    if not source.enabled:
        job.status = "failed"
        job.error_summary = "source is disabled"
        return
    if source.allowed_use_policy not in ("permitted_fetch", "licensed_api", "public_dataset"):
        job.status = "failed"
        job.error_summary = "source use policy no longer permits automated refresh"
        return
    # MVP: no external fetch. Counters stay zero; partial is honest, not success.
    job.records_seen = job.records_created = job.records_updated = job.records_rejected = 0
    job.status = "partial"
    job.error_summary = NO_FETCH_REASON


def drain_queued_jobs(limit: int = BATCH_SIZE) -> int:
    """Claim and finish up to ``limit`` queued jobs; returns the number processed.

    Safe to call from the scheduler thread, a test, or an operator shell: each job
    is claimed with ``FOR UPDATE SKIP LOCKED`` so concurrent drains never collide.
    """
    db = SessionLocal()
    processed = 0
    try:
        jobs = db.scalars(
            select(IngestionJob)
            .where(IngestionJob.status == "queued")
            .order_by(IngestionJob.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for job in jobs:
            job.status = "running"
            job.started_at = _now()
            job.worker_version = WORKER_VERSION
            db.flush()
            _process_job(db, job)
            job.finished_at = _now()
            db.commit()
            processed += 1
            logger.info("job %s (%s) -> %s", job.id, job.job_type, job.status)
    except Exception:  # pragma: no cover - defensive: never kill the scheduler thread
        db.rollback()
        logger.exception("drain_queued_jobs failed")
    finally:
        db.close()
    return processed


def start_scheduler() -> BackgroundScheduler | None:
    """Start the polling scheduler when enabled; returns the scheduler or None."""
    if not settings.enable_scheduler:
        return None
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(drain_queued_jobs, "interval", seconds=POLL_SECONDS,
                      id="drain_queued_jobs", max_instances=1, coalesce=True)
    scheduler.start()
    logger.info("background job scheduler started (poll every %ss)", POLL_SECONDS)
    return scheduler
