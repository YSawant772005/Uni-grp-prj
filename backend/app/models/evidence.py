"""Source registry and the provenance/fact-history model.

Every critical value in the catalogue can be traced to a fact_record -> fact_version ->
fact_evidence -> source_document -> source chain. Prior versions remain immutable.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPk
from app.models.enums import (
    AllowedUsePolicy,
    FetchStatus,
    GroupOperator,
    IntakeTerm,
    RecordStatus,
    SourceType,
    enum_col,
)


class Source(Base, UUIDPk, TimestampMixin):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("authority_tier BETWEEN 1 AND 5", name="ck_sources_authority_tier"),
        Index("ix_sources_enabled", "enabled"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type = enum_col(SourceType)
    authority_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    owner_or_publisher: Mapped[str | None] = mapped_column(String(200))
    allowed_use_policy = enum_col(AllowedUsePolicy)
    terms_url: Mapped[str | None] = mapped_column(Text)
    robots_policy_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rate_limit_notes: Mapped[str | None] = mapped_column(Text)
    license_notes: Mapped[str | None] = mapped_column(Text)
    refresh_interval_hours: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", default=False)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)


class SourceDocument(Base, UUIDPk):
    __tablename__ = "source_documents"
    __table_args__ = (
        Index("ix_source_documents_source_retrieved", "source_id", "retrieved_at"),
        Index("ix_source_documents_content_hash", "content_hash"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(300))
    document_type: Mapped[str | None] = mapped_column(String(60))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    etag: Mapped[str | None] = mapped_column(String(200))
    last_modified: Mapped[str | None] = mapped_column(String(200))
    storage_uri: Mapped[str | None] = mapped_column(Text)
    content_excerpt: Mapped[str | None] = mapped_column(Text)
    parser_version: Mapped[str | None] = mapped_column(String(40))
    fetch_status = enum_col(FetchStatus, default=FetchStatus.fetched)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FactRecord(Base, UUIDPk, TimestampMixin):
    """Stable identity of one fact about one entity (e.g. program tuition amount)."""

    __tablename__ = "fact_records"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "fact_key", "applicability_key",
            name="uq_fact_records_identity",
        ),
        Index("ix_fact_records_entity", "entity_type", "entity_id"),
        Index("ix_fact_records_status", "current_status"),
    )

    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    fact_key: Mapped[str] = mapped_column(String(80), nullable=False)
    applicability_key: Mapped[str] = mapped_column(String(80), nullable=False, server_default="")
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fact_versions.id", ondelete="SET NULL", use_alter=True, name="fk_fact_records_current_version")
    )
    current_status = enum_col(RecordStatus, default=RecordStatus.candidate)


class FactVersion(Base, UUIDPk):
    __tablename__ = "fact_versions"
    __table_args__ = (
        UniqueConstraint("fact_record_id", "version_number", name="uq_fact_versions_number"),
        Index("ix_fact_versions_record", "fact_record_id"),
        CheckConstraint("version_number > 0", name="ck_fact_versions_positive_number"),
        CheckConstraint(
            "extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)",
            name="ck_fact_versions_confidence_range",
        ),
    )

    fact_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fact_records.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    value_json: Mapped[dict | None] = mapped_column(JSONB)
    normalized_value_json: Mapped[dict | None] = mapped_column(JSONB)
    status = enum_col(RecordStatus, default=RecordStatus.candidate)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    applicable_intake_year: Mapped[int | None] = mapped_column(SmallInteger)
    applicable_intake_term = enum_col(IntakeTerm, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(40))
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FactEvidence(Base, UUIDPk):
    __tablename__ = "fact_evidence"
    __table_args__ = (Index("ix_fact_evidence_version", "fact_version_id"),)

    fact_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fact_versions.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="RESTRICT"), nullable=False
    )
    evidence_excerpt: Mapped[str | None] = mapped_column(Text)
    evidence_locator: Mapped[str | None] = mapped_column(String(300))
    supports_or_conflicts: Mapped[str] = mapped_column(String(20), nullable=False, server_default="supports")
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FactReviewEvent(Base, UUIDPk):
    __tablename__ = "fact_review_events"
    __table_args__ = (
        CheckConstraint(
            "action <> 'reject' OR (reason IS NOT NULL AND length(btrim(reason)) > 0)",
            name="ck_fact_review_events_reject_reason",
        ),
        Index("ix_fact_review_events_record", "fact_record_id"),
    )

    fact_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fact_records.id", ondelete="CASCADE"), nullable=False
    )
    fact_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fact_versions.id", ondelete="SET NULL")
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
