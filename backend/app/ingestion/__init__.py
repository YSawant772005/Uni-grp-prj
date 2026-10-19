"""Ingestion engine for UniShortlist.

Importable entry points: :func:`app.ingestion.pipeline.run_source` (API/worker)
and ``python -m app.ingestion.cli`` (operator shell).
"""
from app.ingestion.pipeline import RunOptions, RunSummary, enqueue_due_refreshes, run_all, run_source

__all__ = ["RunOptions", "RunSummary", "run_source", "run_all", "enqueue_due_refreshes"]