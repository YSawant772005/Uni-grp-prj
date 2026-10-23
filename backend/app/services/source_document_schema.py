"""Runtime compatibility helpers for the additive source-freshness migration."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session, undefer

from app.models import SourceDocument


@lru_cache(maxsize=8)
def _source_document_columns(engine: Engine) -> frozenset[str]:
    return frozenset(column["name"] for column in
                     inspect(engine).get_columns("source_documents", schema="public"))


def freshness_columns_available(db: Session) -> bool:
    required = {"source_published_at", "academic_period", "last_checked_at",
                "last_content_changed_at"}
    return required <= _source_document_columns(db.get_bind())


def source_document_options(db: Session) -> list:
    """Load freshness metadata only when the additive migration is present."""
    if not freshness_columns_available(db):
        return []
    return [undefer(SourceDocument.source_published_at),
            undefer(SourceDocument.academic_period),
            undefer(SourceDocument.last_checked_at),
            undefer(SourceDocument.last_content_changed_at)]


def retrieval_history_available(db: Session) -> bool:
    return inspect(db.get_bind()).has_table("source_document_retrievals", schema="public")


def freshness_values(db: Session, document: SourceDocument) -> dict:
    """Avoid presenting legacy retrieval time as a current freshness check."""
    if not freshness_columns_available(db):
        return {"source_published_at": None, "academic_period": None,
                "last_checked_at": None, "last_content_changed_at": None,
                "freshness_metadata_available": False}
    return {
        "source_published_at": (document.source_published_at.isoformat()
                                 if document.source_published_at else None),
        "academic_period": document.academic_period,
        "last_checked_at": (document.last_checked_at.isoformat()
                            if document.last_checked_at else None),
        "last_content_changed_at": (document.last_content_changed_at.isoformat()
                                    if document.last_content_changed_at else None),
        "freshness_metadata_available": True,
    }
