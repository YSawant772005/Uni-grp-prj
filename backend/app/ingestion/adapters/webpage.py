"""Generic connector for permitted official university/government web pages.

Configuration-driven, so a new university, country or programme catalogue can be
added by configuration alone — there is no country allowlist anywhere in the code.
The connector prefers structured data and downloadable files over HTML: set
``document_type`` to ``json``/``csv`` when the publisher offers them.

Guardrails enforced here:
* only ``http``/``https`` URLs are fetched, and ``robots.txt`` is honoured;
* every extracted value is tied to the passage it was read from, which is stored
  as evidence with a locator;
* nothing is invented — a label that is not present yields no fact at all.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from typing import Iterator

from app.ingestion.adapters.base import RunContext, SourceAdapter
from app.ingestion.extract import (
    csv_to_dicts,
    find_labelled_value,
    html_to_text,
    json_path,
    json_to_dict,
    pdf_to_text,
)
from app.ingestion.http import FetchError
from app.ingestion.normalize import clean_text, normalize_url
from app.ingestion.types import (
    AdapterBatch,
    CandidateFact,
    CandidateInstitution,
    CandidateProgram,
    SourceDoc,
)

logger = logging.getLogger("uni.ingestion")


@dataclass
class FieldRule:
    """One labelled (or JSON-keyed) value to read from a source document."""

    fact_key: str
    label: str | None = None
    kind: str = "text"
    json_path: str | None = None
    column: str | None = None
    applicability_key: str = ""
    confidence: float = 1.0


@dataclass
class WebPageConfig:
    url: str
    document_type: str = "html"          # html | json | csv | pdf
    institution: dict = field(default_factory=dict)
    program: dict | None = None
    rules: list[FieldRule] = field(default_factory=list)
    respect_robots: bool = True
    canonical_url: str | None = None
    title: str | None = None


class WebPageAdapter(SourceAdapter):
    """Reads one permitted public document into a candidate institution."""

    def __init__(self, source_key: str, config: WebPageConfig):
        self.source_key = source_key
        self.config = config

    def iter_batches(self, ctx: RunContext) -> Iterator[AdapterBatch]:
        url = self.config.url
        if urlsplit(url).scheme not in ("http", "https"):
            raise FetchError(url, "only http(s) sources are supported", None, permanent=True)
        if self.config.respect_robots and not _robots_allows(ctx, url):
            logger.warning("robots.txt disallows %s", url)
            return
        result = ctx.fetcher.get(url)
        doc = SourceDoc(url=url, canonical_url=self.config.canonical_url,
                        title=self.config.title, document_type=self.config.document_type,
                        content=result.content, http_status=result.status,
                        etag=result.etag, last_modified=result.last_modified)
        candidate, warnings = self._parse(result.content, doc)
        yield AdapterBatch(document=doc, institutions=[candidate], warnings=warnings)

    # ------------------------------------------------------------------ parsing
    def _parse(self, content: bytes, doc: SourceDoc) -> tuple[CandidateInstitution, list[str]]:
        inst = self.config.institution
        key = inst.get("external_key") or self.config.url
        candidate = CandidateInstitution(
            external_key=key,
            name=clean_text(inst.get("name")) or "UNKNOWN",
            identifiers={k: str(v) for k, v in (inst.get("identifiers") or {}).items()},
            aliases=list(inst.get("aliases") or []),
            country_code=clean_text(inst.get("country_code")),
            country_name=clean_text(inst.get("country_name")),
            region=clean_text(inst.get("region")),
            city=clean_text(inst.get("city")),
            admin_region=clean_text(inst.get("admin_region")),
            address=clean_text(inst.get("address")),
            website=normalize_url(inst.get("website")) or normalize_url(doc.url),
        )
        warnings: list[str] = []
        if self.config.program:
            spec = self.config.program
            candidate.programs.append(CandidateProgram(
                external_key=spec.get("external_key") or f"{key}:program",
                title=clean_text(spec.get("title")) or "UNKNOWN",
                degree_level=spec.get("degree_level", "masters"),
                discipline_code=spec.get("discipline_code"),
                discipline_name=spec.get("discipline_name"),
                official_url=normalize_url(spec.get("official_url")) or doc.canonical,
                delivery_language=spec.get("delivery_language"),
                study_mode=spec.get("study_mode"),
                duration_min_months=spec.get("duration_min_months"),
                duration_max_months=spec.get("duration_max_months"),
            ))
        text = None
        rows: list[dict] = []
        payload = None
        kind = self.config.document_type
        if kind == "html":
            text = html_to_text(content.decode("utf-8", errors="replace"))
        elif kind == "pdf":
            text = pdf_to_text(content)
            if text is None:
                warnings.append("PDF text extraction unavailable for this document")
        elif kind == "json":
            payload = json_to_dict(content)
        elif kind == "csv":
            rows = csv_to_dicts(content)
        else:
            warnings.append(f"unsupported document_type {kind!r}")

        for rule in self.config.rules:
            value, passage = self._read(rule, text, payload, rows)
            if value is None or value == "":
                warnings.append(f"rule {rule.fact_key}: label not found in source document")
                continue
            candidate.facts.append(CandidateFact(
                fact_key=rule.fact_key, value={"value": value}, normalized={"value": value},
                applicability_key=rule.applicability_key, excerpt=passage,
                locator=doc.canonical, confidence=rule.confidence,
                extraction_method="parser"))
        return candidate, warnings

    @staticmethod
    def _read(rule: FieldRule, text: str | None, payload, rows: list[dict]):
        if rule.json_path and payload is not None:
            value = json_path(payload, rule.json_path)
            return (None, None) if value is None else (str(value), f"{rule.json_path}={value}")
        if rule.column and rows:
            for row in rows:
                if rule.column in row and row[rule.column]:
                    return row[rule.column].strip(), f"{rule.column}={row[rule.column]}"
            return None, None
        if rule.label and text:
            found = find_labelled_value(text, rule.label, rule.kind)
            return found if found else (None, None)
        return None, None


def _robots_allows(ctx: RunContext, url: str) -> bool:
    cache = ctx.checkpoint.setdefault("robots", {})
    parts = urlsplit(url)
    origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    if origin not in cache:
        parser = RobotFileParser()
        robots_url = origin + "/robots.txt"
        try:
            result = ctx.fetcher.get(robots_url)
            parser.parse(result.text().splitlines())
        except FetchError:
            parser.parse([])  # no robots.txt served: nothing is disallowed
        cache[origin] = parser
    parser: RobotFileParser = cache[origin]
    return parser.can_fetch(ctx.fetcher.user_agent, url)