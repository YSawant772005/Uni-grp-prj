"""Shared Pydantic schemas: pagination envelope, money, provenance."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MoneyAmount(ORMModel):
    """Money always carries amount (nullable = unknown), currency and period."""
    amount: Decimal | None = None
    currency: str | None = None
    period: str | None = None
    academic_year: str | None = None
    status: str


class SourceBrief(ORMModel):
    source_id: uuid.UUID
    title: str | None = None
    url: str | None = None
    retrieved_at: datetime | None = None
    verified_at: datetime | None = None


class FactProvenance(BaseModel):
    """Compact provenance object for a critical fact (API_Contract §4.5)."""
    status: str
    source: SourceBrief | None = None


def pagination_params(page: int = 1, page_size: int = 20) -> tuple[int, int]:
    return max(page, 1), min(max(page_size, 1), 100)


def page_envelope(items: list, page: int, page_size: int, total_items: int) -> dict:
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": (total_items + page_size - 1) // page_size if page_size else 0,
    }
