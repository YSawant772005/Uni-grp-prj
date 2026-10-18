"""Eligibility/recommendation runs and student-owned lists.

A completed run is immutable: re-running creates a new run so historical results stay
reproducible and explainable.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPk
from app.models.enums import EvalStatus, EligibilityStatus, JobStatus, enum_col


class RecommendationRuleset(Base, UUIDPk):
    __tablename__ = "recommendation_rulesets"

    version: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    eligibility_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    scoring_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", default=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecommendationRun(Base, UUIDPk):
    __tablename__ = "recommendation_runs"
    __table_args__ = (Index("ix_recommendation_runs_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("student_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    profile_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ruleset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendation_rulesets.id", ondelete="RESTRICT"), nullable=False
    )
    data_snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status = enum_col(JobStatus, default=JobStatus.queued)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_hash: Mapped[str | None] = mapped_column(String(64))
    result_summary: Mapped[dict | None] = mapped_column(JSONB)
    warning_summary: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecommendationItem(Base, UUIDPk):
    __tablename__ = "recommendation_items"
    __table_args__ = (
        Index("ix_recommendation_items_run_id", "run_id"),
        Index("ix_recommendation_items_run_tier", "run_id", "tier"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    tier: Mapped[str | None] = mapped_column(String(20))
    eligibility_status = enum_col(EligibilityStatus)
    fit_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    reason_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    concerns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    missing_information: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    family_score_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RequirementEvaluation(Base, UUIDPk):
    __tablename__ = "requirement_evaluations"

    recommendation_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendation_items.id", ondelete="CASCADE"), nullable=False
    )
    admission_requirement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("admission_requirements.id", ondelete="RESTRICT"), nullable=False
    )
    status = enum_col(EvalStatus)
    applicant_value_json: Mapped[dict | None] = mapped_column(JSONB)
    expected_value_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_fact_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fact_versions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SavedProgram(Base):
    __tablename__ = "saved_programs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programs.id", ondelete="CASCADE"), primary_key=True
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Comparison(Base, UUIDPk, TimestampMixin):
    __tablename__ = "comparisons"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(160))


class ComparisonItem(Base):
    __tablename__ = "comparison_items"
    __table_args__ = (CheckConstraint("position >= 1", name="ck_comparison_items_position"),)

    comparison_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("comparisons.id", ondelete="CASCADE"), primary_key=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programs.id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
