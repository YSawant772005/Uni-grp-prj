"""Catalogue: universities, campuses, programs, intakes, requirements, fees.

Requirement/fee rows carry a source fact FK so a shown value can always be traced back
to evidence, and a missing amount is never treated as zero or as verified.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPk
from app.models.enums import (
    DegreeLevel,
    FeeType,
    GroupOperator,
    InstitutionType,
    IntakeStatus,
    IntakeTerm,
    MoneyPeriod,
    Operator,
    PublicationStatus,
    RecognitionStatus,
    RecordStatus,
    RequirementType,
    StudyMode,
    enum_col,
)


class University(Base, UUIDPk, TimestampMixin):
    __tablename__ = "universities"
    __table_args__ = (Index("ix_universities_country", "country_code"),)

    canonical_name: Mapped[str] = mapped_column(String(250), nullable=False)
    slug: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"), nullable=False)
    official_website_url: Mapped[str | None] = mapped_column(Text)
    institution_type = enum_col(InstitutionType, nullable=True)
    recognition_status = enum_col(
        RecognitionStatus, default=RecognitionStatus.unknown, server_default=RecognitionStatus.unknown.value
    )
    external_identifiers: Mapped[dict | None] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Campus(Base, UUIDPk, TimestampMixin):
    __tablename__ = "campuses"
    __table_args__ = (Index("ix_campuses_university", "university_id"),)

    university_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("universities.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(200))
    city_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cities.id", ondelete="SET NULL"))
    address_public: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))


class Program(Base, UUIDPk, TimestampMixin):
    __tablename__ = "programs"
    __table_args__ = (
        UniqueConstraint("university_id", "slug", "degree_level", name="uq_programs_identity"),
        CheckConstraint(
            "duration_min_months IS NULL OR duration_max_months IS NULL "
            "OR duration_min_months <= duration_max_months",
            name="ck_programs_duration_order",
        ),
        Index("ix_programs_country", "country_code"),
        Index("ix_programs_publication", "publication_status"),
        Index("ix_programs_field_level", "field_id", "degree_level"),
    )

    university_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("universities.id", ondelete="CASCADE"), nullable=False
    )
    campus_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("campuses.id", ondelete="SET NULL"))
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(250), nullable=False)
    slug: Mapped[str] = mapped_column(String(250), nullable=False)
    degree_level = enum_col(DegreeLevel)
    field_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("fields.id", ondelete="SET NULL"))
    description: Mapped[str | None] = mapped_column(Text)
    official_program_url: Mapped[str | None] = mapped_column(Text)
    delivery_language: Mapped[str | None] = mapped_column(String(16))
    study_mode = enum_col(StudyMode, nullable=True)
    duration_min_months: Mapped[int | None] = mapped_column(SmallInteger)
    duration_max_months: Mapped[int | None] = mapped_column(SmallInteger)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    publication_status = enum_col(
        PublicationStatus, default=PublicationStatus.candidate, server_default=PublicationStatus.candidate.value
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProgramIntake(Base, UUIDPk, TimestampMixin):
    __tablename__ = "program_intakes"
    __table_args__ = (
        UniqueConstraint("program_id", "intake_year", "intake_term", name="uq_program_intakes_identity"),
        CheckConstraint(
            "application_deadline IS NULL OR application_open_date IS NULL "
            "OR application_open_date <= application_deadline",
            name="ck_program_intakes_open_close_order",
        ),
        CheckConstraint(
            "start_date IS NULL OR application_deadline IS NULL OR application_deadline <= start_date",
            name="ck_program_intakes_deadline_before_start",
        ),
        Index("ix_program_intakes_program_year", "program_id", "intake_year"),
    )

    program_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programs.id", ondelete="CASCADE"), nullable=False
    )
    intake_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    intake_term = enum_col(IntakeTerm)
    application_open_date: Mapped[date | None] = mapped_column(Date)
    application_deadline: Mapped[date | None] = mapped_column(Date)
    start_date: Mapped[date | None] = mapped_column(Date)
    is_open_for_applications: Mapped[bool | None] = mapped_column()
    status = enum_col(IntakeStatus, default=IntakeStatus.unknown, server_default=IntakeStatus.unknown.value)


class AdmissionRequirement(Base, UUIDPk, TimestampMixin):
    __tablename__ = "admission_requirements"
    __table_args__ = (Index("ix_admission_requirements_program", "program_id"),)

    program_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programs.id", ondelete="CASCADE"), nullable=False
    )
    program_intake_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("program_intakes.id", ondelete="SET NULL")
    )
    requirement_type = enum_col(RequirementType)
    requirement_key: Mapped[str] = mapped_column(String(80), nullable=False)
    operator = enum_col(Operator)
    expected_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    group_key: Mapped[str | None] = mapped_column(String(60))
    group_operator = enum_col(GroupOperator, nullable=True)
    applicability_notes: Mapped[str | None] = mapped_column(Text)
    source_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fact_records.id", ondelete="SET NULL")
    )


class ProgramFee(Base, UUIDPk, TimestampMixin):
    __tablename__ = "program_fees"
    __table_args__ = (
        CheckConstraint(
            "amount IS NULL OR (amount >= 0 AND currency IS NOT NULL AND period IS NOT NULL)",
            name="ck_program_fees_amount_requires_currency_period",
        ),
        Index("ix_program_fees_program_type", "program_id", "fee_type"),
    )

    program_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programs.id", ondelete="CASCADE"), nullable=False
    )
    program_intake_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("program_intakes.id", ondelete="SET NULL")
    )
    fee_type = enum_col(FeeType)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    period = enum_col(MoneyPeriod, nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(16))
    student_category: Mapped[str | None] = mapped_column(String(40))
    is_mandatory: Mapped[bool | None] = mapped_column(nullable=True)
    status = enum_col(
        RecordStatus, default=RecordStatus.unverified, server_default=RecordStatus.unverified.value
    )
    fact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fact_records.id", ondelete="SET NULL")
    )
