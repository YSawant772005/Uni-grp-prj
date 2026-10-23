"""Versioned reference directory snapshots; never academic approval records."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DirectoryRelease(Base):
    __tablename__ = 'directory_releases'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('source_documents.id', ondelete='RESTRICT'))
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DirectoryInstitution(Base):
    __tablename__ = 'directory_institutions'
    __table_args__ = (Index('ix_directory_country_name', 'release_id', 'country_code', 'name'),
                     Index('ix_directory_match_status', 'release_id', 'match_status'))
    release_id: Mapped[str] = mapped_column(String(64), ForeignKey('directory_releases.id', ondelete='RESTRICT'), primary_key=True)
    ror_id: Mapped[str] = mapped_column(String(9), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2))
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    record_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    match_status: Mapped[str] = mapped_column(String(40), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reconciliation: Mapped[dict] = mapped_column(JSONB, nullable=False)
