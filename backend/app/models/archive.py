"""Independent immutable catalogue snapshots, without FKs into active entities."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CatalogueResetOperation(Base):
    __tablename__ = "catalogue_reset_operations"
    __table_args__ = (CheckConstraint("length(backup_sha256) = 64", name="ck_catalogue_reset_backup_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    operator: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    original_revision: Mapped[str] = mapped_column(String(32), nullable=False)
    backup_path: Mapped[str] = mapped_column(Text, nullable=False)
    backup_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)


class CatalogueArchiveRecord(Base):
    __tablename__ = "catalogue_archive_records"
    __table_args__ = (CheckConstraint("length(row_sha256) = 64", name="ck_catalogue_archive_row_hash"),)

    operation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalogue_reset_operations.id", ondelete="RESTRICT"), primary_key=True)
    table_name: Mapped[str] = mapped_column(String(80), primary_key=True)
    record_key: Mapped[str] = mapped_column(String(250), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    row_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
