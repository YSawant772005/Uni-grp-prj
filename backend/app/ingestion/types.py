"""Value objects exchanged between source adapters and the ingestion pipeline.

Adapters never touch the ORM. They emit documents (what was retrieved, from
where) plus normalized candidate records (what was observed, with a locator).
The pipeline is the only layer that writes to PostgreSQL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class SourceDoc:
    """One retrieved source document (kept in memory; only hash/excerpt persist)."""

    url: str
    title: str | None = None
    document_type: str = "html"
    content: bytes = b""
    http_status: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    source_date: date | None = None
    academic_period: str | None = None
    canonical_url: str | None = None

    @property
    def canonical(self) -> str:
        return self.canonical_url or self.url


@dataclass
class CandidateFact:
    fact_key: str
    value: dict
    normalized: dict | None = None
    applicability_key: str = ""
    excerpt: str | None = None
    locator: str | None = None
    confidence: float | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    status: str = "candidate"
    extraction_method: str = "parser"

    def norm(self) -> dict:
        return self.normalized if self.normalized is not None else self.value


@dataclass
class CandidateProgram:
    external_key: str
    title: str
    degree_level: str = "masters"
    discipline_code: str | None = None
    discipline_name: str | None = None
    official_url: str | None = None
    duration_min_months: int | None = None
    duration_max_months: int | None = None
    study_mode: str | None = None
    delivery_language: str | None = None
    facts: list[CandidateFact] = field(default_factory=list)


@dataclass
class CandidateInstitution:
    external_key: str
    name: str
    identifiers: dict[str, str] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    country_code: str | None = None
    country_name: str | None = None
    region: str | None = None
    city: str | None = None
    admin_region: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    address: str | None = None
    website: str | None = None
    institution_type: str | None = None
    facts: list[CandidateFact] = field(default_factory=list)
    programs: list[CandidateProgram] = field(default_factory=list)
    #: When True the record only enriches an institution that already exists in
    #: the catalogue; a source that carries facts but no identity (and no real
    #: name) must never create placeholder catalogue rows.
    require_existing: bool = False


@dataclass
class CandidateField:
    """Official taxonomy entry (e.g. an NCES CIP series) used for disciplines."""

    key: str
    display_name: str
    description: str | None = None


@dataclass
class AdapterBatch:
    document: SourceDoc
    institutions: list[CandidateInstitution] = field(default_factory=list)
    fields: list[CandidateField] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SourceNotPermitted(RuntimeError):
    """Raised when a source's policy/terms do not allow the requested operation."""


class CandidateRejected(Exception):
    def __init__(self, field: str, code: str, message: str):
        super().__init__(message)
        self.field, self.code, self.message = field, code, message