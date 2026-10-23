"""Ingestion engine for UniShortlist.

Importable entry points: :func:`app.ingestion.pipeline.run_source` (API/worker)
and ``python -m app.ingestion.cli`` (operator shell).
"""
__all__ = ["RunOptions", "RunSummary", "run_source", "run_all", "enqueue_due_refreshes"]


def __getattr__(name):
    # Parsing/normalization and read-only review services must not instantiate a
    # runtime write session merely because they import an ingestion helper.
    if name in __all__:
        from app.ingestion import pipeline
        return getattr(pipeline, name)
    raise AttributeError(name)
