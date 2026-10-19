"""Persistence for the ingestion pipeline.

Writes only through the existing schema, preserving the provenance chain
``Source -> SourceDocument -> FactRecord -> FactVersion -> FactEvidence`` and
never overwriting a historical fact version. All new facts land as
``candidate`` (official source retrieved, awaiting human review); a machine
never marks a fact ``verified`` and never publishes a catalogue row.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone

from sqlalchemy import bindparam, exists, func, select
from sqlalchemy.orm import aliased
from sqlalchemy.orm import Session

from app.db.base import slugify
from app.ingestion.normalize import domain_of, name_key, stable_json
from app.ingestion.types import (
    CandidateFact,
    CandidateInstitution,
    CandidateProgram,
    SourceDoc,
)
from app.models import (
    City,
    Country,
    FactEvidence,
    FactRecord,
    FactVersion,
    Field,
    Program,
    Source,
    SourceDocument,
    University,
)

VERIFIED = "verified"

#: Identifier namespaces whose values are guaranteed to name exactly one
#: institution. Other identifiers (OPEID, EIN, FIPS, ...) are stored for
#: traceability but never used to merge records, because their values repeat
#: across institutions and would silently fuse unrelated universities.
IDENTITY_NAMESPACES = frozenset({
    "ror", "ror_grid", "ror_isni", "ror_wikidata", "ror_ringgold",
    "ipeds_unitid", "grid", "isni", "wikidata",
})


@dataclass
class Counters:
    seen: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    review: int = 0
    skipped: int = 0
    documents: int = 0
    documents_unchanged: int = 0
    fields: int = 0
    validation_errors: list = dc_field(default_factory=list)
    http_failures: list = dc_field(default_factory=list)
    warnings: list = dc_field(default_factory=list)

    def merge(self, other: "Counters") -> None:
        for name in ("seen", "created", "updated", "unchanged", "rejected", "review", "skipped",
                     "documents", "documents_unchanged", "fields"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.validation_errors.extend(other.validation_errors)
        self.http_failures.extend(other.http_failures)
        self.warnings.extend(other.warnings)

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ("seen", "created", "updated", "unchanged", "rejected", "review",
                 "skipped", "documents", "documents_unchanged", "fields")}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _excerpt(content: bytes | None, limit: int = 2000) -> str | None:
    """Readable prefix of a retrieved document (binary-safe, PostgreSQL-text-safe)."""
    if not content:
        return None
    text = content[:limit].decode("utf-8", errors="replace")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return text.strip() or None


# --------------------------------------------------------------------- sources

def ensure_source(db: Session, spec) -> Source:
    """Return the ``sources`` row for this connector.

    Registry metadata lives in code, so an existing row is re-synced with the
    current spec (policy, interval, enabled state); operational health written by
    the pipeline is preserved.
    """
    source = db.scalar(select(Source).where(
        Source.metadata_json["adapter_key"].astext == spec.source_key))
    if source is None:
        source = Source(
            name=spec.name, base_url=spec.base_url.rstrip("/"), source_type=spec.source_type,
            authority_tier=spec.authority_tier, owner_or_publisher=spec.owner_or_publisher,
            allowed_use_policy=spec.allowed_use_policy, terms_url=spec.terms_url,
            license_notes=spec.license_notes, refresh_interval_hours=spec.refresh_interval_hours,
            rate_limit_notes=spec.rate_limit_notes, enabled=spec.enabled,
            metadata_json=source_metadata(spec))
        db.add(source)
        db.flush()
        return source
    meta = dict(source.metadata_json or {})
    health = meta.get("health")
    source.name = spec.name
    source.base_url = spec.base_url.rstrip("/")
    source.source_type = spec.source_type
    source.authority_tier = spec.authority_tier
    source.owner_or_publisher = spec.owner_or_publisher
    source.allowed_use_policy = spec.allowed_use_policy
    source.terms_url = spec.terms_url
    source.license_notes = spec.license_notes
    source.rate_limit_notes = spec.rate_limit_notes
    source.refresh_interval_hours = spec.refresh_interval_hours
    meta.update(source_metadata(spec))
    meta["health"] = health if health is not None else meta.get("health")
    source.metadata_json = meta
    db.flush()
    return source


def source_metadata(spec) -> dict:
    """Registry metadata persisted on the source row (single place of truth)."""
    return {
        "adapter_key": spec.source_key, "supported_data": list(spec.supported_data),
        "country_scope": spec.country_scope, "integration_status": spec.integration_status,
        "request_rps": spec.request_rps, "max_workers": spec.max_workers,
        "timeout_seconds": spec.timeout_seconds,
        "fetch_permitted": spec.allowed_use_policy in
        ("permitted_fetch", "licensed_api", "public_dataset"),
        "notes": spec.notes,
        "health": {"last_success_at": None, "last_failure_at": None, "last_error": None,
                   "consecutive_failures": 0},
    }


def mark_source_health(db: Session, source: Source, *, ok: bool, error: str | None = None) -> None:
    meta = dict(source.metadata_json or {})
    health = dict(meta.get("health") or {})
    if ok:
        health["last_success_at"] = _now().isoformat()
        health["last_error"] = None
        health["consecutive_failures"] = 0
        health["status"] = "healthy"
    else:
        health["last_failure_at"] = _now().isoformat()
        health["last_error"] = (error or "unknown error")[:1000]
        health["consecutive_failures"] = int(health.get("consecutive_failures") or 0) + 1
        health["status"] = "degraded"
    meta["health"] = health
    source.metadata_json = meta


# ------------------------------------------------------------------- documents

def store_document(db: Session, source: Source, doc: SourceDoc, counters: Counters
                   ) -> SourceDocument:
    """Store (or reuse) the retrieved document. The content hash drives change detection."""
    digest = hashlib.sha256(doc.content).hexdigest() if doc.content else None
    if digest:
        existing = db.scalar(select(SourceDocument).where(
            SourceDocument.source_id == source.id,
            SourceDocument.canonical_url == doc.canonical,
            SourceDocument.content_hash == digest))
        if existing is not None:
            counters.documents_unchanged += 1
            return existing
    record = SourceDocument(
        source_id=source.id, canonical_url=doc.canonical, title=doc.title,
        document_type=doc.document_type, content_hash=digest,
        http_status=doc.http_status, fetch_status="fetched", parser_version="ingestion-1",
        etag=doc.etag, last_modified=doc.last_modified, content_excerpt=_excerpt(doc.content))
    db.add(record)
    db.flush()
    counters.documents += 1
    return record


# ------------------------------------------------------------------ reference

def ensure_country(db: Session, code: str | None, name: str | None,
                   region: str | None = None, cache: dict | None = None) -> Country | None:
    if not code or len(code) != 2:
        return None
    if cache is not None and code in cache:
        return cache[code]
    country = db.get(Country, code)
    if country is None:
        if not name:
            return None
        country = Country(code=code, name=name[:120], region=region)
        db.add(country)
        db.flush([country])  # FK target must exist before rows referencing it
    if cache is not None:
        cache[code] = country
    return country


def ensure_field(db: Session, key: str, display_name: str,
                 description: str | None = None) -> Field:
    field = db.scalar(select(Field).where(Field.key == key))
    if field is None:
        field = Field(id=uuid.uuid4(), key=key, display_name=display_name[:160],
                      description=description)
        db.add(field)
        db.flush()
    return field


def ensure_city(db: Session, country_code: str, name: str | None,
                admin_region: str | None = None, cache: dict | None = None) -> City | None:
    if not name:
        return None
    slug = slugify(f"{name}-{admin_region}" if admin_region else name)
    key = (country_code, slug)
    if cache is not None and key in cache:
        return cache[key]
    city = db.scalar(select(City).where(City.country_code == country_code, City.slug == slug))
    if city is None:
        city = City(id=uuid.uuid4(), country_code=country_code, name=name[:160],
                    slug=slug[:180], admin_region=admin_region)
        db.add(city)
        db.flush([city])  # campuses reference cities
    if cache is not None:
        cache[key] = city
    return city


# -------------------------------------------------------------- institution IO

class InstitutionResolver:
    """In-memory identity index: external ids, name+country and website domain.

    Synthetic demo fixtures are deliberately excluded so real source data is
    never merged into (or silently relabelled as) fixture rows.
    """

    def __init__(self, db: Session):
        self.by_identifier: dict[tuple[str, str], uuid.UUID] = {}
        self.by_name: dict[tuple[str, str], uuid.UUID] = {}
        self.by_domain: dict[tuple[str, str], uuid.UUID] = {}
        self.objects: dict[uuid.UUID, University] = {}
        rows = db.execute(
            select(University.id, University.canonical_name, University.country_code,
                   University.official_website_url, University.external_identifiers)
        ).all()
        for uid, name, country, website, identifiers in rows:
            ids = identifiers or {}
            if ids.get("demo_fixture"):
                continue
            self.by_name[(country, name_key(name))] = uid
            domain = domain_of(website)
            if domain and country:
                self.by_domain.setdefault((country, domain), uid)
            for namespace, value in ids.items():
                if _is_identity_namespace(namespace) and isinstance(value, str):
                    self.by_identifier[(namespace, value)] = uid

    def resolve(self, candidate: CandidateInstitution) -> tuple[uuid.UUID | None, str | None]:
        """Resolve a candidate to an existing institution.

        Only an unambiguous external identifier is accepted as a match. Name and
        website-domain lookups are reported as suggestions for review, never applied:
        real, distinct universities do share names and domains.
        """
        for namespace, value in candidate.identifiers.items():
            if not _is_identity_namespace(namespace):
                continue
            found = self.by_identifier.get((namespace, value))
            if found:
                return found, "external_id"
        key = (candidate.country_code or "", name_key(candidate.name))
        if key in self.by_name:
            return self.by_name[key], "name_country"
        domain = domain_of(candidate.website)
        if domain and (candidate.country_code or "", domain) in self.by_domain:
            return self.by_domain[(candidate.country_code or "", domain)], "website_domain"
        return None, None

    def learn(self, university: University) -> None:
        uid = university.id
        self.objects[uid] = university
        identifiers = university.external_identifiers or {}
        self.by_name[(university.country_code, name_key(university.canonical_name))] = uid
        domain = domain_of(university.official_website_url)
        if domain:
            self.by_domain.setdefault((university.country_code, domain), uid)
        for namespace, value in identifiers.items():
            if _is_identity_namespace(namespace) and isinstance(value, str):
                self.by_identifier[(namespace, value)] = uid


def _is_identity_namespace(namespace: str) -> bool:
    return namespace in IDENTITY_NAMESPACES


def _unique_slug(db: Session, model, base: str, **filters) -> str:
    """Slug that is free both in the database and among rows added this session."""
    slug = slugify(base, 200)
    attempt = 1
    while True:
        candidate = slug if attempt == 1 else f"{slug}-{attempt}"
        query = select(model.id).where(model.slug == candidate)
        for column, value in filters.items():
            query = query.where(getattr(model, column) == value)
        taken_in_db = db.scalar(query) is not None
        taken_in_session = any(getattr(row, "slug", None) == candidate
                               for row in db.new | db.dirty)
        if not taken_in_db and not taken_in_session:
            return candidate
        attempt += 1


def upsert_institution(db: Session, candidate: CandidateInstitution,
                       resolver: InstitutionResolver, *,
                       country_cache: dict | None = None,
                       city_cache: dict | None = None) -> tuple[University, str]:
    """Create or update the university row and merge its external identifiers.

    Reference rows (country, city) are written before the university, because the
    university carries a foreign key to them.
    """
    existing_id, match = resolver.resolve(candidate)
    # Only a strong external identifier may reuse an existing institution. Two real
    # universities can share a name (or even a website domain) without being the same
    # institution; merging them would fuse unrelated records and let their facts
    # overwrite each other on every run.
    if existing_id and match != "external_id":
        existing_id, match = None, None
    if existing_id:
        university = resolver.objects.get(existing_id) or db.get(University, existing_id)
        identifiers = dict(university.external_identifiers or {})
        changed = False
        for namespace, value in candidate.identifiers.items():
            if identifiers.get(namespace) != value:
                identifiers[namespace] = value
                changed = True
        if changed:
            university.external_identifiers = identifiers
        if not university.official_website_url and candidate.website:
            university.official_website_url = candidate.website
        if university.institution_type is None and candidate.institution_type:
            university.institution_type = candidate.institution_type
        action = "updated" if changed else "unchanged"
    else:
        ensure_country(db, candidate.country_code, candidate.country_name, candidate.region,
                       country_cache)
        if candidate.city:
            ensure_city(db, candidate.country_code or "US", candidate.city,
                        candidate.admin_region, city_cache)
        slug = _unique_slug(db, University, f"{candidate.name}-{candidate.country_code or 'xx'}")
        university = University(
            id=uuid.uuid4(), canonical_name=candidate.name[:250], slug=slug,
            country_code=candidate.country_code or "US",
            official_website_url=candidate.website,
            institution_type=candidate.institution_type,
            external_identifiers=dict(candidate.identifiers))
        db.add(university)
        action = "created"
    resolver.learn(university)
    return university, action


def upsert_program(db: Session, university: University, candidate: CandidateProgram,
                   fields_by_key: dict[str, uuid.UUID]) -> tuple[Program, str]:
    slug = slugify(candidate.title, 200)
    existing = db.scalar(select(Program).where(
        Program.university_id == university.id, Program.slug == slug,
        Program.degree_level == candidate.degree_level))
    if existing:
        return existing, "unchanged"
    field_id = None
    if candidate.discipline_code:
        field_id = fields_by_key.get(f"cip_{candidate.discipline_code.split('.')[0]}")
    if university in db.new:
        db.flush([university])  # the program carries a foreign key to the university
    program = Program(
        id=uuid.uuid4(), university_id=university.id, country_code=university.country_code,
        canonical_name=candidate.title[:250], slug=slug,
        degree_level=candidate.degree_level, field_id=field_id,
        official_program_url=candidate.official_url,
        delivery_language=(candidate.delivery_language or "")[:16] or None,
        study_mode=candidate.study_mode,
        duration_min_months=candidate.duration_min_months,
        duration_max_months=candidate.duration_max_months,
        publication_status="candidate")
    db.add(program)
    return program, "created"


# ----------------------------------------------------------------------- facts

def add_evidence(db: Session, queued: list[tuple[uuid.UUID, SourceDocument, CandidateFact]]
                 ) -> None:
    """Attach queued evidence rows after the versions they point at are flushed."""
    for version_id, document, fact in queued:
        db.add(FactEvidence(id=uuid.uuid4(), fact_version_id=version_id,
                            source_document_id=document.id, evidence_excerpt=fact.excerpt,
                            evidence_locator=fact.locator,
                            supports_or_conflicts="supports"))
    queued.clear()


def finalize_records(db: Session, pending: list[tuple[FactRecord, uuid.UUID]]) -> None:
    """Point new fact records at their first version once the versions exist.

    ``fact_records.current_version_id`` and ``fact_versions.fact_record_id``
    reference each other, so the pointer can only be written after the version
    row is in the table.
    """
    for record, version_id in pending:
        record.current_version_id = version_id
    pending.clear()


def record_facts(db: Session, *, entity_type: str, entity_id: uuid.UUID, source: Source,
                 document: SourceDocument, facts: list[CandidateFact], counters: Counters,
                 entity_is_new: bool = False, evidence_queue: list | None = None,
                 pending_records: list | None = None, memo: dict | None = None) -> list[str]:
    """Record several facts for one entity.

    When the entity was created in this run no fact can exist for it yet, so the
    records and versions are written without any read; existing entities take the
    careful compare/version/conflict path.
    """
    if not entity_is_new:
        return [record_fact(db, entity_type=entity_type, entity_id=entity_id, source=source,
                            document=document, fact=fact, counters=counters,
                            evidence_queue=evidence_queue,
                            pending_records=pending_records, memo=memo)
                for fact in facts]
    if not facts:
        return []
    for fact in facts:
        state = _FactState(uuid.uuid4(), None, 0, fact.norm(), fact.status, True)
        if memo is not None:
            memo[(entity_type, str(entity_id), fact.fact_key, fact.applicability_key)] = state
        _create_fact(db, entity_type=entity_type, entity_id=entity_id, value=fact.value,
                     normalized=fact.norm(), fact=fact, state=state, document=document,
                     evidence_queue=evidence_queue, pending_records=pending_records)
    counters.created += len(facts)
    return ["created"] * len(facts)


_max_version = select(func.max(FactVersion.version_number)).where(
    FactVersion.fact_record_id == FactRecord.id).correlate(FactRecord).scalar_subquery()
_current_version = aliased(FactVersion)
_evidence_exists = exists(select(FactEvidence.id).where(
    FactEvidence.fact_version_id == FactRecord.current_version_id,
    FactEvidence.source_document_id == bindparam("document_id")))
# Which source published the value currently in force. Two sources disagreeing about
# the same value is a conflict to route to review, not something to overwrite forever.
_current_source = select(SourceDocument.source_id).where(
    SourceDocument.id == FactEvidence.source_document_id,
    FactEvidence.fact_version_id == FactRecord.current_version_id
).limit(1).correlate(FactRecord).scalar_subquery()
# Has this source already published exactly this value for this fact? (idempotency
# across runs when the value in force came from a different source)
_already_recorded = exists(
    select(FactEvidence.id)
    .join(SourceDocument, SourceDocument.id == FactEvidence.source_document_id)
    .join(FactVersion, FactVersion.id == FactEvidence.fact_version_id)
    .where(FactVersion.fact_record_id == FactRecord.id,
           SourceDocument.source_id == bindparam("source_id"),
           FactVersion.normalized_value_json == bindparam("normalized"))
)


def _lookup(db: Session, *, entity_type: str, entity_id: uuid.UUID, fact: CandidateFact,
            document: SourceDocument, normalized: dict, source_id: uuid.UUID):
    """One query: the fact record, its current version, the next version number,
    whether this document is already attached as evidence, which source published
    the value in force, and whether this source already published this value."""
    return db.execute(
        select(FactRecord, _current_version.version_number, _current_version.value_json,
               _current_version.normalized_value_json, _current_version.status,
               _max_version.label("max_version"), _evidence_exists.label("evidence_exists"),
               _current_source.label("current_source_id"),
               _already_recorded.label("already_recorded"))
        .outerjoin(_current_version, _current_version.id == FactRecord.current_version_id)
        .where(FactRecord.entity_type == entity_type, FactRecord.entity_id == entity_id,
               FactRecord.fact_key == fact.fact_key,
               FactRecord.applicability_key == fact.applicability_key)
        .params(document_id=document.id, source_id=source_id, normalized=normalized)
    ).first()


class _FactState:
    """In-memory view of one fact record for the current flush window."""

    __slots__ = ("record_id", "current_version_id", "normalized", "status",
                 "max_version", "evidence_exists", "obj", "current_source_id",
                 "already_recorded")

    def __init__(self, record_id, current_version_id, max_version, normalized, status,
                 evidence_exists, obj=None, current_source_id=None, already_recorded=False):
        self.record_id = record_id
        self.current_version_id = current_version_id
        self.max_version = max_version
        self.normalized = normalized
        self.status = status
        self.evidence_exists = evidence_exists
        self.obj = obj
        self.current_source_id = current_source_id
        # this source already published exactly this value in an earlier version,
        # so re-running it must not append the same conflicting version again
        self.already_recorded = already_recorded


def _load_fact_state(row) -> "_FactState":
    record = row[0]
    return _FactState(record.id, record.current_version_id, row[5] or row[1] or 0,
                      row[3] or row[2], row[4], bool(row[6]), obj=record,
                      current_source_id=row[7], already_recorded=bool(row[8]))


def record_fact(db: Session, *, entity_type: str, entity_id: uuid.UUID, source: Source,
                document: SourceDocument, fact: CandidateFact, counters: Counters,
                evidence_queue: list | None = None,
                pending_records: list | None = None,
                memo: dict | None = None) -> str:
    """Idempotent fact write with versioning, conflict detection and evidence.

    One query resolves the fact record, its current version, the highest version
    number and whether this document is already attached as evidence, so a re-run
    costs one round trip per fact instead of four. ``memo`` caches that answer for
    the current flush window, so two candidates resolving to the same entity in one
    batch cannot both append the same version number.
    """
    value = fact.value
    normalized = fact.norm()
    key = (entity_type, str(entity_id), fact.fact_key, fact.applicability_key)
    # Direct callers (tests, one-off scripts) get immediate durability; the
    # pipeline passes queues/memo and flushes once per document instead.
    direct = pending_records is None and evidence_queue is None
    state = memo.get(key) if memo is not None else None
    if state is None:
        row = _lookup(db, entity_type=entity_type, entity_id=entity_id, fact=fact,
                      document=document, normalized=normalized, source_id=source.id)
        state = _load_fact_state(row) if row is not None else _FactState(
            uuid.uuid4(), None, 0, normalized, fact.status, True)
        if memo is not None:
            memo[key] = state
        if row is None:
            _create_fact(db, entity_type=entity_type, entity_id=entity_id, value=value,
                         normalized=normalized, fact=fact, state=state, document=document,
                         evidence_queue=evidence_queue, pending_records=pending_records)
            if direct:
                db.flush()
            counters.created += 1
            return "created"

    if state.current_version_id is not None and \
            stable_json(state.normalized) == stable_json(normalized):
        # A second source confirming the same value is corroboration, not a change.
        if not state.evidence_exists:
            _queue_evidence(evidence_queue, state.current_version_id, document, fact, db)
            state.evidence_exists = True
            if state.current_source_id is None:
                state.current_source_id = source.id
        if direct:
            db.flush()
        counters.unchanged += 1
        return "unchanged"

    # A different source publishing a different value for a fact that no reviewer
    # has settled is a genuine conflict: record both, route to review, keep the value
    # already in force. Overwriting here would make two sources overwrite each other
    # on every run, which is neither idempotent nor honest.
    other_source = state.current_source_id is not None and \
        state.current_source_id != source.id
    if other_source and state.already_recorded:
        # this source already published this exact value: re-running it changes nothing
        counters.unchanged += 1
        return "unchanged"
    conflicted = state.status == VERIFIED or other_source
    next_number = state.max_version + 1
    version = _add_version(db, state.record_id, next_number, value, normalized, fact,
                           status="conflicted" if conflicted else fact.status)
    if direct:
        db.flush()  # evidence and the pointer FK both need the version row to exist
    fact_record = state.obj or db.get(FactRecord, state.record_id)
    fact_record.current_status = "conflicted" if conflicted else fact.status
    if not conflicted:
        if pending_records is None:
            fact_record.current_version_id = version.id
        else:
            pending_records.append((fact_record, version.id))
        state.current_version_id = version.id
        state.normalized = normalized
        state.max_version = next_number
        state.status = fact.status
        state.current_source_id = source.id
    else:
        state.max_version = next_number
        state.already_recorded = True
    _queue_evidence(evidence_queue, version.id, document, fact, db)
    if direct:
        db.flush()
    counters.review += 1 if conflicted else 0
    counters.updated += 1
    return "review" if conflicted else "updated"


def _create_fact(db: Session, *, entity_type: str, entity_id: uuid.UUID, value: dict,
                 normalized: dict, fact: CandidateFact, state: "_FactState",
                 document: SourceDocument, evidence_queue: list | None,
                 pending_records: list | None) -> FactVersion:
    version_id = uuid.uuid4()
    record = FactRecord(id=state.record_id, entity_type=entity_type, entity_id=entity_id,
                        fact_key=fact.fact_key, applicability_key=fact.applicability_key,
                        current_status=fact.status)
    db.add(record)
    state.obj = record
    version = FactVersion(id=version_id, fact_record_id=state.record_id, version_number=1,
                          value_json=value, normalized_value_json=normalized,
                          status=fact.status, extraction_method=fact.extraction_method,
                          extraction_confidence=fact.confidence,
                          effective_from=fact.effective_from,
                          effective_to=fact.effective_to, created_at=_now())
    direct = pending_records is None
    if direct:
        db.flush()  # the version's FK needs the record to exist first
    db.add(version)
    if direct:
        db.flush()  # evidence and the current-version pointer need the version
    _queue_evidence(evidence_queue, version_id, document, fact, db if direct else None)
    if direct:
        record.current_version_id = version_id
    else:
        pending_records.append((record, version_id))
    state.current_version_id = version_id
    state.max_version = 1
    state.current_source_id = document.source_id
    return version


def _queue_evidence(queue, version_id: uuid.UUID, document: SourceDocument,
                    fact: CandidateFact, db: Session | None = None) -> None:
    if queue is not None:
        queue.append((version_id, document, fact))
    elif db is not None:
        db.add(FactEvidence(id=uuid.uuid4(), fact_version_id=version_id,
                            source_document_id=document.id, evidence_excerpt=fact.excerpt,
                            evidence_locator=fact.locator,
                            supports_or_conflicts="supports"))


def _link_evidence(db: Session, version_id: uuid.UUID | None, document: SourceDocument,
                   fact: CandidateFact) -> None:
    """Attach the retrieved passage once; repeated runs never duplicate evidence."""
    if version_id is None:
        return
    db.add(FactEvidence(id=uuid.uuid4(), fact_version_id=version_id,
                        source_document_id=document.id, evidence_excerpt=fact.excerpt,
                        evidence_locator=fact.locator, supports_or_conflicts="supports"))


def _add_version(db: Session, fact_record_id: uuid.UUID, number: int, value: dict,
                 normalized: dict, fact: CandidateFact, status: str | None = None) -> FactVersion:
    version = FactVersion(id=uuid.uuid4(), fact_record_id=fact_record_id,
                          version_number=number, value_json=value,
                          normalized_value_json=normalized, status=status or fact.status,
                          extraction_method=fact.extraction_method,
                          extraction_confidence=fact.confidence,
                          effective_from=fact.effective_from,
                          effective_to=fact.effective_to, created_at=_now())
    db.add(version)
    return version



def field_index(db: Session) -> dict[str, uuid.UUID]:
    return {key: fid for key, fid in db.execute(select(Field.key, Field.id))}
