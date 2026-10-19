"""Ingestion/refresh jobs. Jobs are idempotent and auditable; nothing auto-publishes."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPk
from app.models.enums import JobItemStatus, JobStatus, JobType, enum_col


class IngestionJob(Base, UUIDPk):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (Index("ix_ingestion_jobs_status", "status"),)

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sources.id", ondelete="SET NULL")
    )
    job_type = enum_col(JobType)
    status = enum_col(JobStatus, default=JobStatus.queued)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_seen: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    records_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    records_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    records_review_required: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    checkpoint: Mapped[dict | None] = mapped_column(JSONB)
    error_summary: Mapped[str | None] = mapped_column(Text)
    worker_version: Mapped[str | None] = mapped_column(String(40))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IngestionJobItem(Base, UUIDPk, TimestampMixin):
    __tablename__ = "ingestion_job_items"
    __table_args__ = (
        Index("ix_ingestion_job_items_job", "job_id"),
        Index("ix_ingestion_job_items_external", "job_id", "entity_type", "external_key", unique=True),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_jobs.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="SET NULL")
    )
    entity_type: Mapped[str | None] = mapped_column(String(40))
    external_key: Mapped[str | None] = mapped_column(String(200))
    status = enum_col(JobItemStatus, default=JobItemStatus.processed)
    candidate_payload: Mapped[dict | None] = mapped_column(JSONB)
    validation_errors: Mapped[dict | None] = mapped_column(JSONB)
    fact_record_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fact_records.id", ondelete="SET NULL")
    )
