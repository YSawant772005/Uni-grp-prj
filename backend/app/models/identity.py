"""Identity, roles, student profiles and audit events."""
from __future__ import annotations

import uuid
from datetime import datetime
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPk
from app.models.enums import (
    ActorType,
    BudgetBasis,
    CountryMode,
    DegreeLevel,
    EnglishTestType,
    GradeSystem,
    GraduationStatus,
    IntakeTerm,
    PriorityKey,
    RoleKey,
    RiskTolerance,
    TestStatus,
    UserStatus,
    enum_col,
)


class User(Base, UUIDPk, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_status", "status"),)

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(120))
    status = enum_col(UserStatus, default=UserStatus.active, server_default="active")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: server-side revocation watermark: tokens issued before this instant are rejected
    tokens_valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    roles: Mapped[list["Role"]] = relationship(
        secondary="user_roles",
        primaryjoin="User.id == UserRole.user_id",
        secondaryjoin="Role.id == UserRole.role_id",
        lazy="selectin",
        viewonly=True,
    )


class Role(Base, UUIDPk, TimestampMixin):
    __tablename__ = "roles"

    key = enum_col(RoleKey, unique=True)
    description: Mapped[str | None] = mapped_column(String(200))


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StudentProfile(Base, UUIDPk, TimestampMixin):
    __tablename__ = "student_profiles"
    __table_args__ = (
        CheckConstraint(
            "budget_amount IS NULL OR budget_amount >= 0",
            name="ck_student_profiles_budget_nonnegative",
        ),
        CheckConstraint(
            "budget_amount IS NULL OR (budget_currency IS NOT NULL AND budget_basis IS NOT NULL)",
            name="ck_student_profiles_budget_currency_basis",
        ),
        CheckConstraint(
            "grade_value IS NULL OR (grade_system IS NOT NULL AND grade_scale_min IS NOT NULL "
            "AND grade_scale_max IS NOT NULL AND grade_scale_min < grade_scale_max "
            "AND grade_value >= grade_scale_min AND grade_value <= grade_scale_max)",
            name="ck_student_profiles_grade_scale",
        ),
        CheckConstraint(
            "backlog_count IS NULL OR backlog_count >= 0",
            name="ck_student_profiles_backlog_nonnegative",
        ),
        CheckConstraint(
            "work_experience_months IS NULL OR work_experience_months >= 0",
            name="ck_student_profiles_experience_nonnegative",
        ),
        CheckConstraint(
            "english_test_overall IS NULL OR english_test_overall >= 0",
            name="ck_student_profiles_test_overall_nonnegative",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    intended_degree_level = enum_col(DegreeLevel, default=DegreeLevel.masters)
    field_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("fields.id", ondelete="SET NULL"))
    country_mode = enum_col(CountryMode, nullable=True)
    risk_tolerance = enum_col(RiskTolerance, nullable=True)

    academic_degree: Mapped[str | None] = mapped_column(String(160))
    academic_major: Mapped[str | None] = mapped_column(String(160))
    institution_name: Mapped[str | None] = mapped_column(String(200))
    grade_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    grade_scale_min: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    grade_scale_max: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    grade_system = enum_col(GradeSystem, nullable=True)
    graduation_status = enum_col(GraduationStatus, nullable=True)
    graduation_year: Mapped[int | None] = mapped_column(SmallInteger)
    backlog_count: Mapped[int | None] = mapped_column(Integer)

    english_test_status = enum_col(TestStatus, nullable=True)
    english_test_type = enum_col(EnglishTestType, nullable=True)
    english_test_overall: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    english_test_component_scores: Mapped[dict | None] = mapped_column(JSONB)
    other_test_scores: Mapped[dict | None] = mapped_column(JSONB)

    work_experience_months: Mapped[int | None] = mapped_column(Integer)
    projects_summary: Mapped[str | None] = mapped_column(Text)
    career_goal: Mapped[str | None] = mapped_column(String(300))

    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    budget_currency: Mapped[str | None] = mapped_column(String(3))
    budget_basis = enum_col(BudgetBasis, nullable=True)
    target_intake_year: Mapped[int | None] = mapped_column(SmallInteger)
    target_intake_term = enum_col(IntakeTerm, nullable=True)

    profile_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    country_preferences: Mapped[list["ProfileCountryPreference"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan",
        order_by="ProfileCountryPreference.preference_rank", lazy="selectin")
    priorities: Mapped[list["ProfilePriority"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan",
        order_by="ProfilePriority.priority_key", lazy="selectin")


class ProfileCountryPreference(Base):
    """Ordered country preferences; a mandatory country is a hard constraint."""

    __tablename__ = "profile_country_preferences"
    __table_args__ = (UniqueConstraint("profile_id", "preference_rank", name="uq_profile_country_rank"),)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("student_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.code"), primary_key=True
    )
    preference_rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    profile: Mapped["StudentProfile"] = relationship(back_populates="country_preferences")


class ProfilePriority(Base, UUIDPk, TimestampMixin):
    __tablename__ = "profile_priorities"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    priority_key = enum_col(PriorityKey)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    __table_args__ = (
        UniqueConstraint("profile_id", "priority_key", name="uq_profile_priority_key"),
        CheckConstraint("weight >= 0 AND weight <= 1", name="ck_profile_priorities_weight_range"),
    )
    profile: Mapped["StudentProfile"] = relationship(back_populates="priorities")


class AuditEvent(Base, UUIDPk):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    actor_type = enum_col(ActorType, default=ActorType.user)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reason: Mapped[str | None] = mapped_column(Text)
    before_summary: Mapped[dict | None] = mapped_column(JSONB)
    after_summary: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
