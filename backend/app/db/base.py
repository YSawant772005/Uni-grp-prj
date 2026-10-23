"""Shared declarative base, mixins and column helpers."""
from __future__ import annotations

import uuid
import re
import unicodedata
from datetime import datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def slugify(text: str, max_len: int = 180) -> str:
    """ASCII slugs for new records; never rewrite a persisted slug on read/update."""
    if max_len < 1:
        raise ValueError("A slug needs a positive maximum length.")
    text = text.casefold().translate(str.maketrans({"ø": "o", "ł": "l", "đ": "d",
                                                   "ð": "d", "þ": "th", "œ": "oe", "æ": "ae"}))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (s[:max_len].rstrip("-") or "item"[:max_len])


__all__ = ["Base", "UUIDPk", "TimestampMixin", "slugify"]
