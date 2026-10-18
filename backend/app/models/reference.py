"""Reference data: countries, cities, field taxonomy."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPk


class Country(Base, TimestampMixin):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    region: Mapped[str | None] = mapped_column(String(80))
    official_study_url: Mapped[str | None] = mapped_column(Text)
    official_immigration_url: Mapped[str | None] = mapped_column(Text)


class City(Base, UUIDPk, TimestampMixin):
    __tablename__ = "cities"
    __table_args__ = (
        UniqueConstraint("country_code", "slug", name="uq_cities_country_slug"),
        Index("ix_cities_country_name", "country_code", "name"),
    )

    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False)
    admin_region: Mapped[str | None] = mapped_column(String(120))


class Field(Base, UUIDPk, TimestampMixin):
    __tablename__ = "fields"

    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_field_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fields.id", ondelete="SET NULL")
    )
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
