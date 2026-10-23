"""Source adapter contract.

An adapter is responsible for: retrieving permitted source documents, parsing
them into candidate records, and attaching the source URL / locator to every
value it emits. It must not decide publication, verification or persistence —
those belong to the pipeline and the existing review workflow.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator

from app.ingestion.http import Fetcher
from app.ingestion.types import AdapterBatch, SourceDoc

MAX_PAGES_DEFAULT = 10_000


@dataclass
class RunContext:
    """Everything an adapter needs; nothing else. Adapters stay reusable."""

    fetcher: Fetcher
    countries: list[str] | None = None
    max_records: int | None = None
    max_pages: int = MAX_PAGES_DEFAULT
    checkpoint: dict = field(default_factory=dict)
    dry_run: bool = False
    offline: bool = False
    query: str | None = None


@dataclass
class AdapterSpec:
    """Declarative source-registry entry (also used to seed the ``sources`` table)."""

    source_key: str
    name: str
    base_url: str
    source_type: str
    authority_tier: int
    allowed_use_policy: str
    owner_or_publisher: str
    license_notes: str
    terms_url: str | None = None
    refresh_interval_hours: int | None = None
    enabled: bool = False
    supported_data: tuple[str, ...] = ()
    country_scope: str = "global"
    integration_status: str = "active"
    rate_limit_notes: str | None = None
    request_rps: float = 5.0
    max_workers: int = 4
    timeout_seconds: float = 60.0
    notes: str | None = None
    requires_explicit_limit: bool = False


class SourceAdapter(ABC):
    source_key: str

    @abstractmethod
    def iter_batches(self, ctx: RunContext) -> Iterator[AdapterBatch]:
        """Yield retrieved document + parsed candidates. Must be lazy."""

    @staticmethod
    def document_from_http(url: str, result, **kwargs) -> SourceDoc:
        return SourceDoc(url=url, content=result.content, http_status=result.status,
                         etag=result.etag, last_modified=result.last_modified,
                         retrieval_attempt_count=getattr(result, "attempts", 1), **kwargs)
