"""Currency conversion using fixed dated reference rates (MVP has no live FX provider).

Every conversion returns the value, the rate used, and its date so the UI can label
derived figures as estimated rather than verified.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FxRate


class Conversion:
    __slots__ = ("amount", "currency", "rate", "rate_date", "rate_source")

    def __init__(self, amount, currency, rate, rate_date, rate_source):
        self.amount = amount
        self.currency = currency
        self.rate = rate
        self.rate_date = rate_date
        self.rate_source = rate_source


def get_rate(db: Session, base: str, quote: str) -> FxRate | None:
    if base == quote:
        return None  # identity; no rate row needed
    return db.scalar(
        select(FxRate)
        .where(FxRate.base_currency == base, FxRate.quote_currency == quote)
        .order_by(FxRate.rate_date.desc())
        .limit(1)
    )


def convert(db: Session, amount, base: str, quote: str) -> Conversion | None:
    """Convert ``amount`` from ``base`` to ``quote``; None when amount or rate unknown."""
    if amount is None or base is None or quote is None:
        return None
    if base == quote:
        return Conversion(Decimal(amount), quote, Decimal("1"), None, "identity")
    row = get_rate(db, base, quote)
    if row is None:
        return None
    return Conversion((Decimal(amount) * row.rate).quantize(Decimal("0.01")), quote,
                      row.rate, row.rate_date, row.source)


def has_rate(db: Session, base: str, quote: str) -> bool:
    return base == quote or get_rate(db, base, quote) is not None
