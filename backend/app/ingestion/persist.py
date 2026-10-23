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
from collections import defaultdict
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
    InstitutionIdentityReview,
    InstitutionIdentifier,
    InstitutionReview,
    Program,
    ProgramIdentifier,
    Source,
    SourceDocument,
    SourceDocumentRetrieval,
    University,
)

VERIFIED = "verified"

#: Identifier namespaces whose values are guaranteed to name exactly one
#: institution. Other identifiers (OPEID, EIN, FIPS, ...) are stored for
#: traceability but never used to merge records, because their values repeat
#: across institutions and would silently fuse unrelated universities.
IDENTITY_NAMESPACES = frozenset({
    "ror", "ror_grid", "ror_isni", "ror_wikidata", "ror_ringgold",
    "ipeds_unitid", "uai", "rio_provider_id", "grid", "isni", "wikidata",
})


@dataclass
class Counters:
    seen: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    review: int = 0
    conflicted: int = 0
    skipped: int = 0
    documents: int = 0
    documents_unchanged: int = 0
    fields: int = 0
    institutions_seen: int = 0
    institutions_created: int = 0
    institutions_updated: int = 0
    institutions_unchanged: int = 0
    programs_seen: int = 0
    programs_created: int = 0
    programs_updated: int = 0
    programs_unchanged: int = 0
    programs_rejected: int = 0
    programs_review_required: int = 0
    validation_errors: list = dc_field(default_factory=list)
    http_failures: list = dc_field(default_factory=list)
    warnings: list = dc_field(default_factory=list)

    def merge(self, other: "Counters") -> None:
        for name in ("seen", "created", "updated", "unchanged", "rejected", "review", "conflicted", "skipped",
                     "documents", "documents_unchanged", "fields", "institutions_seen",
                     "institutions_created", "institutions_updated", "institutions_unchanged",
                     "programs_seen", "programs_created", "programs_updated",
                     "programs_unchanged", "programs_rejected", "programs_review_required"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.validation_errors.extend(other.validation_errors)
        self.http_failures.extend(other.http_failures)
        self.warnings.extend(other.warnings)

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ("seen", "created", "updated", "unchanged", "rejected", "review", "conflicted",
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
    schedule = meta.get("refresh_schedule")
    meta.update(source_metadata(spec))
    if schedule is not None:
        meta["refresh_schedule"] = schedule
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
        "requires_explicit_limit": spec.requires_explicit_limit,
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
    """Store one immutable content snapshot and append a retrieval/check event."""
    digest = hashlib.sha256(doc.content).hexdigest() if doc.content else None
    checked_at = _now()
    was_checked_now = doc.retrieval_attempt_count > 0
    latest = db.scalar(select(SourceDocument).where(
        SourceDocument.source_id == source.id,
        SourceDocument.canonical_url == doc.canonical,
    ).order_by(SourceDocument.last_checked_at.desc(), SourceDocument.id.desc()).limit(1))
    if digest:
        existing = db.scalar(select(SourceDocument).where(
            SourceDocument.source_id == source.id,
            SourceDocument.canonical_url == doc.canonical,
            SourceDocument.content_hash == digest))
        if existing is not None:
            if was_checked_now:
                existing.last_checked_at = checked_at
                if latest is not None and latest.content_hash != digest:
                    existing.last_content_changed_at = checked_at
            if doc.source_date is not None:
                existing.source_published_at = doc.source_date
            if doc.academic_period:
                existing.academic_period = doc.academic_period
            if was_checked_now and doc.etag:
                existing.etag = doc.etag
            if was_checked_now and doc.last_modified:
                existing.last_modified = doc.last_modified
            if was_checked_now:
                _record_retrieval(db, source, existing, doc, digest)
                _mark_source_check(source, checked_at, changed=(latest is not None and latest.content_hash != digest))
            db.flush()
            counters.documents_unchanged += 1
            return existing
    record = SourceDocument(
        source_id=source.id, canonical_url=doc.canonical, title=doc.title,
        document_type=doc.document_type, content_hash=digest,
        source_published_at=doc.source_date, academic_period=doc.academic_period,
        retrieved_at=doc.retrieved_at or checked_at,
        last_checked_at=doc.retrieved_at or checked_at,
        last_content_changed_at=doc.retrieved_at or checked_at,
        http_status=doc.http_status, fetch_status="fetched", parser_version="ingestion-1",
        etag=doc.etag, last_modified=doc.last_modified,
        content_excerpt=doc.content_excerpt or _excerpt(doc.content))
    db.add(record)
    db.flush()
    if was_checked_now:
        _record_retrieval(db, source, record, doc, digest)
        _mark_source_check(source, checked_at, changed=(latest is None or latest.content_hash != digest))
    db.flush()
    counters.documents += 1
    return record


def _record_retrieval(db: Session, source: Source, document: SourceDocument | None,
                      doc: SourceDoc, digest: str | None,
                      *, outcome: str | None = None, error: str | None = None) -> None:
    outcome = outcome or ("not_modified" if doc.http_status == 304 else "fetched")
    db.add(SourceDocumentRetrieval(
        source_id=source.id, source_document_id=document.id if document else None,
        canonical_url=doc.canonical, outcome=outcome, http_status=doc.http_status,
        attempt_count=max(1, doc.retrieval_attempt_count), content_hash=digest,
        etag=doc.etag, last_modified=doc.last_modified,
        error_summary=(error[:2000] if error else None)))


def _mark_source_check(source: Source, checked_at: datetime, *, changed: bool) -> None:
    meta = dict(source.metadata_json or {})
    health = dict(meta.get("health") or {})
    health["last_checked_at"] = checked_at.isoformat()
    if changed:
        health["last_content_changed_at"] = checked_at.isoformat()
    meta["health"] = health
    source.metadata_json = meta


def record_failed_retrieval(db: Session, source: Source, url: str, error: str,
                            *, http_status: int | None = None, attempt_count: int = 1) -> None:
    """Persist an external retrieval failure separately from immutable content snapshots."""
    db.add(SourceDocumentRetrieval(
        source_id=source.id, canonical_url=url, outcome="failed", http_status=http_status,
        attempt_count=max(1, attempt_count), error_summary=error[:2000]))
    meta = dict(source.metadata_json or {})
    health = dict(meta.get("health") or {})
    health["last_checked_at"] = _now().isoformat()
    meta["health"] = health
    source.metadata_json = meta


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
    key = (country_code, name, admin_region)
    if cache is not None and key in cache:
        return cache[key]
    # A slug is not place identity: different Unicode names may normalize to
    # the same ASCII value. Exact matches also preserve legacy filter slugs.
    city = db.scalar(select(City).where(City.country_code == country_code,
        City.name == name[:160], City.admin_region == admin_region).order_by(City.id).limit(1))
    if city is None:
        slug = _unique_slug(db, City, f"{name}-{admin_region}" if admin_region else name,
                            max_len=180, country_code=country_code)
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
        self.by_identifier: dict[tuple[str, str, str], set[uuid.UUID]] = defaultdict(set)
        # Weak hints are sets: a display name or domain can legitimately refer
        # to more than one canonical institution and must never pick a winner.
        self.by_name: dict[tuple[str, str], set[uuid.UUID]] = defaultdict(set)
        self.by_domain: dict[tuple[str, str], set[uuid.UUID]] = defaultdict(set)
        self.objects: dict[uuid.UUID, University] = {}
        self.approved_links: dict[tuple[uuid.UUID, str], uuid.UUID] = {
            (source_id, external_key): university_id
            for source_id, external_key, university_id in db.execute(select(
                InstitutionIdentityReview.source_id,
                InstitutionIdentityReview.external_key,
                InstitutionIdentityReview.resolved_university_id,
            ).where(InstitutionIdentityReview.status == "approved",
                    InstitutionIdentityReview.resolved_university_id.is_not(None))).all()
        }
        rows = db.execute(
            select(University.id, University.canonical_name, University.country_code,
                   University.official_website_url, University.external_identifiers)
        ).all()
        for uid, name, country, website, identifiers in rows:
            ids = identifiers or {}
            if ids.get("demo_fixture"):
                continue
            self.by_name[(country, name_key(name))].add(uid)
            domain = domain_of(website)
            if domain and country:
                self.by_domain[(country, domain)].add(uid)
            for namespace, value in ids.items():
                if _is_identity_namespace(namespace) and isinstance(value, str):
                    self.by_identifier[(namespace, _normalize_identifier(value),
                                        _default_identifier_scope(namespace))].add(uid)
        claims = db.execute(select(
            InstitutionIdentifier.university_id, InstitutionIdentifier.namespace,
            InstitutionIdentifier.normalized_value, InstitutionIdentifier.scope,
        ).where(InstitutionIdentifier.claim_status == "accepted")).all()
        for uid, namespace, value, scope in claims:
            if _is_identity_namespace(namespace):
                self.by_identifier[(namespace, _normalize_identifier(value), scope)].add(uid)

    def resolve(self, candidate: CandidateInstitution,
                source_id: uuid.UUID | None = None) -> tuple[uuid.UUID | None, str | None]:
        """Resolve a candidate to an existing institution.

        Only an unambiguous external identifier is accepted as a match. Name and
        website-domain lookups are reported as suggestions for review, never applied:
        real, distinct universities do share names and domains.
        """
        matched: set[uuid.UUID] = set()
        for namespace, value in candidate.identifiers.items():
            namespace = namespace.strip().lower()
            if not _is_identity_namespace(namespace) or not isinstance(value, str):
                continue
            scope = candidate.identifier_scopes.get(namespace, _default_identifier_scope(namespace))
            found = self.by_identifier.get((namespace, _normalize_identifier(value), scope), set())
            if len(found) > 1:
                return None, "ambiguous_identifier"
            matched.update(found)
        if len(matched) > 1:
            return None, "conflicting_identifiers"
        reviewed = self.approved_links.get((source_id, candidate.external_key)) if source_id else None
        if reviewed is not None:
            if matched and reviewed not in matched:
                return None, "conflicting_identifiers"
            return reviewed, "reviewed_link"
        if matched:
            return next(iter(matched)), "external_id"
        key = (candidate.country_code or "", name_key(candidate.name))
        name_matches = self.by_name.get(key, set())
        domain = domain_of(candidate.website)
        domain_matches = (self.by_domain.get((candidate.country_code or "", domain), set())
                          if domain else set())

        # Name and domain remain review suggestions, never identity proof. If
        # they disagree, or either hint collides, leave the candidate unselected
        # rather than handing a reviewer an arbitrary canonical record.
        if name_matches and domain_matches:
            overlap = name_matches & domain_matches
            if len(overlap) == 1:
                return next(iter(overlap)), "name_domain"
            return None, "ambiguous_weak_match"
        matches = name_matches or domain_matches
        if len(matches) == 1:
            return next(iter(matches)), "name_country" if name_matches else "website_domain"
        if len(matches) > 1:
            return None, "ambiguous_weak_match"
        return None, None

    def learn(self, university: University) -> None:
        uid = university.id
        self.objects[uid] = university
        identifiers = university.external_identifiers or {}
        self.by_name[(university.country_code, name_key(university.canonical_name))].add(uid)
        domain = domain_of(university.official_website_url)
        if domain:
            self.by_domain[(university.country_code, domain)].add(uid)
        for namespace, value in identifiers.items():
            if _is_identity_namespace(namespace) and isinstance(value, str):
                self.by_identifier[(namespace, _normalize_identifier(value),
                                    _default_identifier_scope(namespace))].add(uid)


def _is_identity_namespace(namespace: str) -> bool:
    return namespace in IDENTITY_NAMESPACES


def _normalize_identifier(value: str) -> str:
    return value.strip().casefold()


def _default_identifier_scope(namespace: str) -> str:
    return "reporting_unit" if namespace in {"ipeds_unitid", "uai", "rio_provider_id"} else "institution"


def _unique_slug(db: Session, model, base: str, *, max_len: int = 200, **filters) -> str:
    """Slug that is free both in the database and among rows added this session."""
    slug = slugify(base, max_len)
    attempt = 1
    while True:
        suffix = "" if attempt == 1 else f"-{attempt}"
        candidate = slug[:max_len-len(suffix)].rstrip("-") + suffix
        query = select(model.id).where(model.slug == candidate)
        for column, value in filters.items():
            query = query.where(getattr(model, column) == value)
        taken_in_db = db.scalar(query) is not None
        taken_in_session = any(isinstance(row, model) and row.slug == candidate
                               and all(getattr(row, column) == value for column, value in filters.items())
                               for row in db.new | db.dirty)
        if not taken_in_db and not taken_in_session:
            return candidate
        attempt += 1


def upsert_institution(db: Session, candidate: CandidateInstitution,
                       resolver: InstitutionResolver, *,
                       source: Source | None = None,
                       source_document: SourceDocument | None = None,
                       country_cache: dict | None = None,
                       city_cache: dict | None = None) -> tuple[University, str]:
    """Create or update the university row and merge its external identifiers.

    Reference rows (country, city) are written before the university, because the
    university carries a foreign key to them.
    """
    existing_id, match = resolver.resolve(candidate, source.id if source else None)
    if match in ("ambiguous_identifier", "conflicting_identifiers"):
        raise ValueError(f"institution identity refused: {match}")
    # Only a strong external identifier may reuse an existing institution. Two real
    # universities can share a name (or even a website domain) without being the same
    # institution; merging them would fuse unrelated records and let their facts
    # overwrite each other on every run.
    if existing_id and match not in ("external_id", "reviewed_link"):
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
    if university in db.new:
        db.flush([university])
    _persist_identifier_claims(db, university, candidate, source, source_document)
    if source is not None and not (university.external_identifiers or {}).get("demo_fixture"):
        review = db.scalar(select(InstitutionReview).where(
            InstitutionReview.university_id == university.id).with_for_update())
        if review is None:
            db.add(InstitutionReview(university_id=university.id, status="pending"))
            db.flush()
    resolver.learn(university)
    return university, action


def _persist_identifier_claims(db: Session, university: University,
                               candidate: CandidateInstitution, source: Source | None,
                               document: SourceDocument | None) -> None:
    source_key = ((source.metadata_json or {}).get("adapter_key") if source else None) or (
        source.name if source else "unspecified")
    for namespace, raw_value in candidate.identifiers.items():
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        namespace = namespace.strip().lower()
        normalized = _normalize_identifier(raw_value)
        scope = candidate.identifier_scopes.get(namespace, _default_identifier_scope(namespace))
        campus_id = candidate.identifier_campus_ids.get(namespace)
        claim = db.scalar(select(InstitutionIdentifier).where(
            InstitutionIdentifier.source_key == source_key,
            InstitutionIdentifier.namespace == namespace,
            InstitutionIdentifier.normalized_value == normalized,
            InstitutionIdentifier.scope == scope,
            InstitutionIdentifier.university_id == university.id,
        ))
        authoritative = namespace in IDENTITY_NAMESPACES
        owner = db.scalar(select(InstitutionIdentifier).where(
            InstitutionIdentifier.namespace == namespace,
            InstitutionIdentifier.normalized_value == normalized,
            InstitutionIdentifier.scope == scope,
            InstitutionIdentifier.claim_status == "accepted").limit(1)) if authoritative else None
        if claim is None and owner is not None:
            if owner.university_id != university.id:
                raise ValueError("authoritative institution identifier belongs to another institution")
            # The uniqueness constraint represents canonical identifier ownership.
            # A second publisher corroborates that owner through versioned facts;
            # it must not insert another accepted owner or replace the first source.
            applicability = hashlib.sha256(f"{source_key}:{namespace}:{normalized}:{scope}".encode()).hexdigest()
            if not any(f.fact_key == "source_identity_claim" and f.applicability_key == applicability
                       for f in candidate.facts):
                candidate.facts.append(CandidateFact(
                    "source_identity_claim", {"namespace": namespace, "identifier": raw_value.strip(), "scope": scope},
                    normalized={"namespace": namespace, "identifier": normalized, "scope": scope},
                    applicability_key=applicability,
                    excerpt=f"{candidate.name}: {namespace}={raw_value.strip()} ({scope})",
                    locator=candidate.external_key))
            continue
        if claim is None:
            db.add(InstitutionIdentifier(
                id=uuid.uuid4(), university_id=university.id,
                source_id=source.id if source else None,
                source_document_id=document.id if document else None,
                source_key=source_key, namespace=namespace,
                identifier_value=raw_value.strip(), normalized_value=normalized,
                scope=scope,
                campus_id=uuid.UUID(campus_id) if campus_id else None,
                claim_status="accepted" if authoritative else "pending_review"))
        elif not authoritative and claim.claim_status == "accepted":
            # Auxiliary registry values (FIPS, EIN, OPEID, etc.) remain traceable
            # but must not masquerade as authoritative canonical identity claims.
            claim.claim_status = "pending_review"
        identifiers = dict(university.external_identifiers or {})
        if identifiers.get(namespace) != raw_value.strip():
            identifiers[namespace] = raw_value.strip()
            university.external_identifiers = identifiers
    db.flush()


def upsert_program(db: Session, university: University, candidate: CandidateProgram,
                   fields_by_key: dict[str, uuid.UUID], *, source: Source,
                   source_document: SourceDocument) -> tuple[Program, str]:
    source_key = (source.metadata_json or {}).get("adapter_key") or source.name
    external_key = candidate.external_key.strip()
    normalized_key = external_key.casefold()
    claim = db.scalar(select(ProgramIdentifier).where(
        ProgramIdentifier.source_key == source_key,
        ProgramIdentifier.normalized_external_key == normalized_key,
    ))
    if claim is not None:
        if claim.claim_status != "accepted":
            raise ValueError("program identity claim is not accepted")
        existing = db.get(Program, claim.program_id)
        if existing is None or existing.university_id != university.id:
            raise ValueError("source program identifier conflicts with its institution mapping")
        if claim.source_document_id != source_document.id:
            claim.source_document_id = source_document.id
            return existing, "updated"
        return existing, "unchanged"

    slug = _unique_slug(db, Program, candidate.title, university_id=university.id)
    field_id = fields_by_key.get(candidate.discipline_key) if candidate.discipline_key else None
    if field_id is None and candidate.discipline_code:
        field_id = fields_by_key.get(f"cip_{candidate.discipline_code.split('.')[0]}")
    if field_id is None and candidate.discipline_name:
        # Only attach a source label when it exactly matches the controlled
        # taxonomy after deterministic normalization. Similar labels stay unset
        # for review rather than being forced into the nearest field.
        field_id = fields_by_key.get(f"name:{name_key(candidate.discipline_name)}")
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
    db.flush([program])
    db.add(ProgramIdentifier(
        program_id=program.id, source_id=source.id, source_document_id=source_document.id,
        source_key=source_key, external_key=external_key,
        normalized_external_key=normalized_key, claim_status="accepted"))
    db.flush()
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
           FactVersion.normalized_value_json == bindparam("normalized"),
           FactVersion.status != "rejected")
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
    if state.already_recorded and (other_source or state.status == VERIFIED):
        # this source already published this exact value: re-running it changes nothing
        counters.unchanged += 1
        return "unchanged"
    conflicted = state.status == VERIFIED or other_source
    if conflicted:
        counters.conflicted += 1
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
                          effective_to=fact.effective_to,
                          applicable_intake_year=fact.applicable_intake_year,
                          applicable_intake_term=fact.applicable_intake_term,
                          created_at=_now())
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
                          effective_to=fact.effective_to,
                          applicable_intake_year=fact.applicable_intake_year,
                          applicable_intake_term=fact.applicable_intake_term,
                          created_at=_now())
    db.add(version)
    return version



def field_index(db: Session) -> dict[str, uuid.UUID]:
    rows = db.execute(select(Field.key, Field.display_name, Field.id))
    index: dict[str, uuid.UUID] = {}
    by_name: dict[str, set[uuid.UUID]] = defaultdict(set)
    for key, display_name, field_id in rows:
        index[key] = field_id
        by_name[name_key(display_name)].add(field_id)
    for label, field_ids in by_name.items():
        if len(field_ids) == 1:
            index[f"name:{label}"] = next(iter(field_ids))
    return index
