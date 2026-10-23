"""Shared checks for program-page evidence used by review and public APIs."""
from __future__ import annotations

import re
from sqlalchemy import select
from sqlalchemy.orm import Session
from urllib.parse import urlsplit

from app.ingestion.normalize import normalize_url, program_title_matches
from app.models import FactEvidence, FactRecord, FactVersion, Program, ProgramIdentifier, Source, SourceDocument, University
from app.services.source_urls import classify_program_url
from app.services.review_readiness import title_key


def _url_established(url: str, document: SourceDocument, evidence: FactEvidence) -> bool:
    # A reviewed URL still needs an observed page or an explicit source link.
    # A passage naming only the degree cannot establish an arbitrary URL.
    return (normalize_url(document.canonical_url) == url
            or url in (evidence.evidence_excerpt or ""))


def supporting_program_page_evidence(db, program, version, url, *, rows=None, accepted_keys=None):
    """One qualification check for explicit URL review and publication."""
    rows = rows if rows is not None else db.execute(select(FactEvidence, SourceDocument, Source)
        .join(SourceDocument, SourceDocument.id == FactEvidence.source_document_id)
        .join(Source, Source.id == SourceDocument.source_id)
        .where(FactEvidence.fact_version_id == version.id)
        .order_by(FactEvidence.created_at, FactEvidence.id)).all()
    supported = []
    value = version.value_json if isinstance(version.value_json, dict) else {}
    for evidence, document, source in rows:
        if (document.fetch_status != 'fetched'
                or document.http_status is not None and not 200 <= document.http_status < 300
                or source.allowed_use_policy not in ('permitted_fetch', 'licensed_api', 'public_dataset')
                or evidence.supports_or_conflicts != 'supports'
                or not evidence.evidence_excerpt or not evidence.evidence_locator
                or not _url_established(url, document, evidence)):
            continue
        if (source.metadata_json or {}).get('adapter_key') == 'ual_masters':
            code, observed, binding = value.get('plan_code'), value.get('page_title'), value.get('plan_binding')
            parts = urlsplit(url)
            claim = ((program.id, source.id, value.get('source_program_key')) in accepted_keys
                     if accepted_keys is not None else db.scalar(select(ProgramIdentifier.id).where(
                ProgramIdentifier.program_id == program.id,
                ProgramIdentifier.source_id == source.id,
                ProgramIdentifier.source_key == 'ual_masters',
                ProgramIdentifier.external_key == value.get('source_program_key'),
                ProgramIdentifier.claim_status == 'accepted')))
            if (not isinstance(code, str) or not code.isdigit()
                    or program.degree_level != 'masters'
                    or value.get('source_program_key') != f'ual:master:plan:{code}'
                    or not claim or not isinstance(observed, str)
                    or '{{' in observed or '{%' in observed
                    or not program_title_matches(program.canonical_name, observed)
                    or title_key(observed) not in title_key(evidence.evidence_excerpt)
                    or not isinstance(binding, str) or binding not in evidence.evidence_excerpt
                    or not re.search(rf"(?:\bvar\s+parameters\s*=\s*\[\s*['\"]{code}['\"]\s*\]|\bdata-plan=['\"]{code}['\"])", binding)
                    or parts.hostname not in ('ual.es', 'www.ual.es')
                    or parts.path.rstrip('/') not in (f'/estudios/masteres/presentacion/{code}',
                                                      f'/en/estudios/masteres/presentacion/{code}')
                    or normalize_url(document.canonical_url) != url):
                continue
        elif title_key(program.canonical_name) not in title_key(evidence.evidence_excerpt):
            continue
        supported.append((evidence, document, source))
    return supported


def official_program_page(db: Session, program: Program, *, context=None, university=None) -> dict:
    """Describe whether the stored URL has an explicitly reviewed source trail.

    A URL on a program row is only a candidate pointer. It is considered verified
    when a reviewer-approved current fact names that exact URL and has fetched
    source evidence. A source catalogue URL or a syntactically valid URL alone is
    not proof of a course-specific page.
    """
    url = normalize_url(program.official_program_url)
    if not url:
        entries = list(context['program_facts'].get(program.id, {}).values()) if context is not None else None
        candidate = (next((entry['record'] for entry in sorted(entries,
                     key=lambda e: (e['record'].updated_at, str(e['record'].id)), reverse=True)
                     if entry['record'].fact_key == 'official_program_page_url'
                     and entry['record'].current_status in ('candidate', 'unverified', 'in_review')), None)
                     if entries is not None else db.scalar(select(FactRecord).where(
            FactRecord.entity_type == 'program', FactRecord.entity_id == program.id,
            FactRecord.fact_key == 'official_program_page_url',
            FactRecord.current_status.in_(('candidate', 'unverified', 'in_review')))
            .order_by(FactRecord.updated_at.desc(), FactRecord.id).limit(1)))
        version = ((context['program_facts'][program.id][candidate.id]['version'] if context is not None
                    else db.get(FactVersion, candidate.current_version_id))
                   if candidate and candidate.current_version_id else None)
        value = version.value_json if version and isinstance(version.value_json, dict) else {}
        candidate_url = normalize_url(value.get('url'))
        if candidate_url:
            return {'status': classify_program_url(candidate_url), 'url': candidate_url,
                    'fact_id': candidate.id,
                    'reason': 'A candidate page URL is available; explicit fact verification is still required.'}
        return {"status": "unavailable", "url": None, "reason": "No program page URL is recorded."}
    classification = classify_program_url(url)
    if classification in {"general_catalogue", "source_api", "dataset_record", "identifier_resolver", "government_program_record"}:
        return {"status": classification, "url": url,
                "reason": "This link identifies a catalogue, source or registry; an individual university course page is unestablished."}

    fact = (next((entry['record'] for entry in context['program_facts'].get(program.id, {}).values()
                  if entry['record'].fact_key == 'official_program_page_url'
                  and entry['record'].current_status == 'verified'), None)
            if context is not None else db.scalar(select(FactRecord).where(
        FactRecord.entity_type == "program", FactRecord.entity_id == program.id,
        FactRecord.fact_key == "official_program_page_url",
        FactRecord.current_status == "verified").limit(1)))
    entry = context['program_facts'][program.id][fact.id] if context is not None and fact else None
    version = ((entry['version'] if entry else db.get(FactVersion, fact.current_version_id))
               if fact and fact.current_version_id else None)
    recorded_url = None
    if version and version.status == "verified" and isinstance(version.value_json, dict):
        recorded_url = normalize_url(version.value_json.get("url"))
    evidence = []
    if fact and version and recorded_url == url:
        evidence = supporting_program_page_evidence(db, program, version, url,
            rows=entry['evidence'] if entry else None,
            accepted_keys=context['accepted_program_keys'] if context is not None else None)
    university = university if university is not None else db.get(University, program.university_id)
    website_host = (urlsplit(normalize_url(university.official_website_url) or "").hostname
                    if university else None)
    page_host = urlsplit(url).hostname
    same_institution = bool(website_host and page_host and
                            (page_host == website_host or page_host.endswith("." + website_host)))
    if evidence and same_institution:
        return {"status": "verified", "url": url, "reason": None,
                "fact_id": fact.id, "version_id": version.id,
                "evidence": [{"source_name": src.name, "source_url": doc.canonical_url,
                              "source_document_id": doc.id,
                              "retrieved_at": doc.retrieved_at.isoformat(),
                              "excerpt": ev.evidence_excerpt, "locator": ev.evidence_locator}
                             for ev, doc, src in evidence]}
    classification = classify_program_url(url)
    return {"status": classification, "url": url,
            "reason": "The exact program page has no reviewer-verified fact with fetched source evidence."}


def public_program_page_url(db: Session, program: Program, university: University) -> str | None:
    """Return only a verified real-program URL; preserve labelled demo fixtures."""
    if (university.external_identifiers or {}).get("demo_fixture"):
        return program.official_program_url
    evidence = official_program_page(db, program)
    return evidence["url"] if evidence["status"] == "verified" else None


def official_registry_page(db: Session, program: Program, *, context=None) -> dict:
    """Keep government offering records distinct from university course pages."""
    rows = ([(entry['record'],entry['version'],*evidence)
             for entry in context['program_facts'].get(program.id,{}).values()
             if entry['record'].fact_key=='official_program_registry_url'
             and entry['record'].current_status=='verified' and entry['version']
             and entry['version'].status=='verified' for evidence in entry['evidence']]
            if context is not None else db.execute(select(FactRecord, FactVersion, FactEvidence, SourceDocument, Source)
        .join(FactVersion, FactVersion.id == FactRecord.current_version_id)
        .join(FactEvidence, FactEvidence.fact_version_id == FactVersion.id)
        .join(SourceDocument, SourceDocument.id == FactEvidence.source_document_id)
        .join(Source, Source.id == SourceDocument.source_id)
        .where(FactRecord.entity_type == "program", FactRecord.entity_id == program.id,
               FactRecord.fact_key == "official_program_registry_url",
               FactRecord.current_status == "verified", FactVersion.status == "verified")))
    for fact, version, evidence, document, source in rows:
        value = version.value_json if isinstance(version.value_json, dict) else {}
        url = normalize_url(value.get("url"))
        from urllib.parse import parse_qs
        parts = urlsplit(url or "")
        registry_identifier = (parse_qs(parts.query).get("CourseCode", [None])[0]
                               if parts.hostname == "cricos.education.gov.au"
                               else parts.path.rstrip("/").rsplit("/", 1)[-1])
        if (classify_program_url(url) != "government_program_record"
                or source.source_type not in ("government", "regulator")
                or source.allowed_use_policy not in ("public_dataset", "licensed_api", "permitted_fetch")
                or document.fetch_status != "fetched"
                or document.http_status is not None and not 200 <= document.http_status < 300
                or evidence.supports_or_conflicts != "supports"
                or not evidence.evidence_excerpt or not evidence.evidence_locator
                or title_key(program.canonical_name) not in title_key(evidence.evidence_excerpt)
                or not _url_established(url, document, evidence)):
            continue
        claim = ((program.id,source.id,value.get('source_program_key')) in context['accepted_program_keys']
                 if context is not None else db.scalar(select(ProgramIdentifier.id).where(
            ProgramIdentifier.program_id == program.id, ProgramIdentifier.claim_status == "accepted",
            ProgramIdentifier.source_id == source.id,
            ProgramIdentifier.external_key == value.get("source_program_key"))))
        source_key = str(value.get("source_program_key") or "")
        if claim and registry_identifier and registry_identifier.casefold() in source_key.casefold().replace("/", ":").split(":"):
            return {"status": "verified_government_program_record", "url": url,
                    "fact_id": fact.id, "source_document_id": document.id,
                    "reason": "Government program record; a university course page is not established."}
    return {"status": "unavailable", "url": None, "reason": "No reviewer-verified government program record is available."}
