"""In-process background worker for ingestion/refresh jobs (APScheduler; no Redis).

Jobs are idempotent and bounded: a queued job is claimed atomically (``FOR UPDATE
SKIP LOCKED``). When the job's source has a registered connector the real
pipeline runs (``app.ingestion``). For a source that has no connector the job
finishes honestly as ``partial`` with a sanitized ``error_summary`` explaining
that nothing was fetched. Nothing here ever marks a fact verified or publishes a
candidate automatically.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.ingestion.pipeline import RunOptions, enqueue_due_refreshes, run_source
from app.ingestion.registry import FETCHABLE_POLICIES, get_adapter
from app.models import IngestionJob, Source

logger = logging.getLogger("uni.api")

WORKER_VERSION = "ingestion-worker-1"
POLL_SECONDS = 15
REFRESH_SCAN_SECONDS = 600
BATCH_SIZE = 5
NO_FETCH_REASON = ("no connector is registered for this source; no content was fetched and "
                   "no candidate facts were created or published")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _process_job(job_id) -> None:
    """Run one claimed job through the registered connector, or fail it honestly."""
    db = SessionLocal()
    try:
        job = db.get(IngestionJob, job_id)
        source = db.get(Source, job.source_id) if job and job.source_id else None
        if source is None:
            _finish(db, job, "failed", "source no longer exists")
            return
        if not source.enabled:
            _finish(db, job, "failed", "source is disabled")
            return
        if source.allowed_use_policy not in FETCHABLE_POLICIES:
            _finish(db, job, "failed",
                    "source use policy no longer permits automated refresh")
            return
        adapter_key = (source.metadata_json or {}).get("adapter_key")
        if not adapter_key or get_adapter(adapter_key) is None:
            _finish(db, job, "partial", NO_FETCH_REASON)
            return
    finally:
        db.close()

    summary = run_source(adapter_key, RunOptions(), job_id=job_id)
    logger.info("job %s (%s) -> %s (%s)", job_id, adapter_key, summary.status, summary.error or "")


def _finish(db, job: IngestionJob | None, status: str, reason: str) -> None:
    if job is None:
        return
    job.status = status
    job.finished_at = _now()
    job.error_summary = reason[:2000]
    job.records_seen = job.records_created = job.records_updated = 0
    job.records_rejected = 0
    job.records_unchanged = 0
    job.records_review_required = 0
    db.commit()


def drain_queued_jobs(limit: int = BATCH_SIZE) -> int:
    """Claim up to ``limit`` queued jobs and process them; returns the count.

    Safe to call from the scheduler thread, a test, or an operator shell: each job
    is claimed with ``FOR UPDATE SKIP LOCKED`` so concurrent drains never collide.
    """
    db = SessionLocal()
    processed = 0
    try:
        job_ids = db.scalars(
            select(IngestionJob.id)
            .where(IngestionJob.status == "queued")
            .order_by(IngestionJob.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for job_id in job_ids:
            job = db.get(IngestionJob, job_id)
            job.status = "running"
            job.started_at = _now()
            job.worker_version = WORKER_VERSION
        db.commit()
    except Exception:  # pragma: no cover - defensive: never kill the scheduler thread
        db.rollback()
        logger.exception("drain_queued_jobs failed")
        db.close()
        return 0
    finally:
        db.close()

    for job_id in job_ids:
        try:
            _process_job(job_id)
        except Exception:  # pragma: no cover - one bad job cannot stop the worker
            logger.exception("job %s failed", job_id)
        processed += 1
    return processed


def queue_due_refreshes() -> int:
    """Queue refreshes for sources whose configured interval has elapsed."""
    db = SessionLocal()
    try:
        queued = enqueue_due_refreshes(db)
        db.commit()
        if queued:
            logger.info("queued %s due source refresh(es)", len(queued))
        return len(queued)
    except Exception:  # pragma: no cover
        db.rollback()
        logger.exception("queue_due_refreshes failed")
        return 0
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    """Start the polling scheduler when enabled; returns the scheduler or None."""
    if not settings.enable_scheduler:
        return None
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(drain_queued_jobs, "interval", seconds=POLL_SECONDS,
                      id="drain_queued_jobs", max_instances=1, coalesce=True)
    scheduler.add_job(queue_due_refreshes, "interval", seconds=REFRESH_SCAN_SECONDS,
                      id="queue_due_refreshes", max_instances=1, coalesce=True)
    scheduler.start()
    logger.info("background job scheduler started (poll every %ss, refresh scan every %ss)",
                POLL_SECONDS, REFRESH_SCAN_SECONDS)
    return scheduler