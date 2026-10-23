"""Official-page reference passages become public summaries only after review."""
import re

from sqlalchemy import func, select

from app.core.errors import ApiError
from app.ingestion.normalize import normalize_url
from app.models import FactEvidence, FactRecord, FactVersion, ProgramIdentifier, University
from app.services.program_evidence import supporting_program_page_evidence
from app.services.source_urls import classify_program_url


def _invalid(message):
    raise ApiError(422, 'INVALID_FACT_PROJECTION', message)


def description_evidence(db, program, version):
    value = version.value_json if isinstance(version.value_json, dict) else {}
    url = normalize_url(value.get('url'))
    excerpt = value.get('source_excerpt')
    university = db.get(University, program.university_id)
    from urllib.parse import urlsplit
    host = urlsplit(normalize_url(university.official_website_url) or '').hostname if university else None
    page_host = urlsplit(url or '').hostname
    if (not url or classify_program_url(url) != 'unverified_candidate'
            or not host or not page_host or not (page_host == host or page_host.endswith('.' + host))
            or not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > 800
            or any(t in excerpt for t in ('{{', '{%', '}}'))):
        return []
    return [(ev, doc, source) for ev, doc, source in supporting_program_page_evidence(db, program, version, url)
        if source.source_type == 'official_university' and doc.document_type == 'html'
        and normalize_url(doc.canonical_url) == url and excerpt in ev.evidence_excerpt
        and db.scalar(select(ProgramIdentifier.id).where(ProgramIdentifier.program_id == program.id,
            ProgramIdentifier.source_id == source.id, ProgramIdentifier.claim_status == 'accepted',
            ProgramIdentifier.external_key == value.get('source_program_key')))]


def validate_summary(summary, excerpt):
    if (not isinstance(summary, str) or not 40 <= len(summary.strip()) <= 600
            or len(summary.split()) > 90 or any(t in summary for t in ('{{', '{%', '}}', '<', '>'))):
        _invalid('Write a plain-text summary of 40–600 characters and at most 90 words; templates and HTML are not descriptions.')
    words = re.findall(r'\w+', summary.casefold())
    source_words = re.findall(r'\w+', excerpt.casefold())
    passages = {tuple(source_words[i:i+12]) for i in range(len(source_words)-11)}
    if any(tuple(words[i:i+12]) in passages for i in range(len(words)-11)):
        _invalid('Write the summary in your own words instead of copying the source passage.')
    return summary.strip()


def prepare_summary_version(db, user, fact, original, summary):
    value = original.value_json if isinstance(original.value_json, dict) else {}
    summary = validate_summary(summary, str(value.get('source_excerpt') or ''))
    version = FactVersion(fact_record_id=fact.id,
        version_number=(db.scalar(select(func.max(FactVersion.version_number)).where(FactVersion.fact_record_id == fact.id)) or 0) + 1,
        value_json={**value, 'summary': summary},
        # Comparison remains based on the source passage. An unchanged import
        # must not replace or requeue the independently written reviewed summary.
        normalized_value_json=original.normalized_value_json or {k: v for k, v in value.items() if k != 'summary'},
        status='candidate', extraction_method='reviewer_summary', created_by_user_id=user.id)
    db.add(version)
    db.flush()
    for evidence in db.scalars(select(FactEvidence).where(FactEvidence.fact_version_id == original.id)):
        db.add(FactEvidence(fact_version_id=version.id, source_document_id=evidence.source_document_id,
            evidence_excerpt=evidence.evidence_excerpt, evidence_locator=evidence.evidence_locator,
            supports_or_conflicts=evidence.supports_or_conflicts, reviewer_note=evidence.reviewer_note))
    db.flush()
    return version


def apply_description(db, program, version):
    value = version.value_json if isinstance(version.value_json, dict) else {}
    summary = validate_summary(value.get('summary'), str(value.get('source_excerpt') or ''))
    if not description_evidence(db, program, version):
        _invalid('A description needs the permitted official HTML page, matching program identity and plan/title evidence.')
    if program.description and program.description.strip() != summary:
        _invalid('An existing description is preserved. This review cannot overwrite authored programme text.')
    program.description = summary
    return 'applied'


def public_description(db, program):
    if not program.description:
        return None, None
    rows = db.execute(select(FactRecord, FactVersion).join(FactVersion, FactVersion.fact_record_id == FactRecord.id)
        .where(FactRecord.entity_type == 'program', FactRecord.entity_id == program.id,
               FactRecord.fact_key == 'program_description')).all()
    managed = False
    for fact, version in rows:
        value = version.value_json if isinstance(version.value_json, dict) else {}
        if version.extraction_method != 'reviewer_summary' or value.get('summary') != program.description:
            continue
        managed = True
        if fact.current_version_id == version.id and fact.current_status == version.status == 'verified':
            evidence = description_evidence(db, program, version)
            if evidence:
                _, document, source = evidence[0]
                return program.description, {'source_name': source.name, 'source_url': document.canonical_url,
                    'retrieved_at': document.retrieved_at, 'verified_at': version.reviewed_at,
                    'attribution': source.owner_or_publisher or source.name,
                    'fact_id': fact.id, 'version_id': version.id}
    # Preserve existing authored text. A withdrawn evidence-managed summary is
    # hidden until reviewed again; its stored text/history is never deleted.
    return (None if managed else program.description), None
