"""Committed metrics, worker execution, conflict replay and schedule approval."""
from sqlalchemy import func, select

from app.ingestion import persist
from app.ingestion.pipeline import RunOptions, enqueue_due_refreshes, run_source
from app.ingestion.types import CandidateFact, CandidateInstitution, SourceDoc
from app.models import FactVersion, IngestionJob, InstitutionIdentifier
from test_ingestion import _batch, _institution, _spec, registered


def test_registered_queued_worker_uses_its_own_session(db, registered):
    spec, adapter = registered
    adapter.batches = [_batch([_institution()])]
    source = persist.ensure_source(db, spec)
    job = IngestionJob(source_id=source.id, job_type="refresh", status="running", checkpoint={"run_options": {"max_records": 1}})
    db.add(job)
    db.commit()
    summary = run_source(spec.source_key, RunOptions(max_records=1), job_id=job.id)
    assert summary.status == "succeeded", summary.error
    db.expire_all()
    stored = db.get(IngestionJob, job.id)
    assert stored.status == "succeeded"
    assert stored.checkpoint["run_options"]["max_records"] == 1


def test_interval_alone_never_authorizes_scheduling(db, registered):
    spec, _ = registered
    spec.refresh_interval_hours = 1
    assert enqueue_due_refreshes(db) == []


def test_changed_verified_fact_does_not_duplicate_conflicts_on_replay(db, registered):
    spec, _ = registered
    source = persist.ensure_source(db, spec)
    university, _ = persist.upsert_institution(db, CandidateInstitution(
        external_key="refresh:u", name="Refresh University", country_code="DE",
        identifiers={"ror": "refresh-identity"}), persist.InstitutionResolver(db), source=source)
    document = persist.store_document(db, source, SourceDoc(url="https://example.org/a", content=b"original"), persist.Counters())
    entity = dict(entity_type="university", entity_id=university.id, source=source, document=document)
    persist.record_fact(db, **entity, fact=CandidateFact("name", {"name": "Old"}, status="verified"), counters=persist.Counters())
    changed = CandidateFact("name", {"name": "Changed"})
    assert persist.record_fact(db, **entity, fact=changed, counters=persist.Counters()) == "review"
    assert persist.record_fact(db, **entity, fact=changed, counters=persist.Counters()) == "unchanged"
    assert db.scalar(select(func.count()).select_from(FactVersion).where(FactVersion.value_json["name"].astext == "Changed")) == 1


def test_second_source_corroborates_the_original_identifier_owner_with_valid_evidence(db):
    from app.services.admin import _source_institution_link
    first = persist.ensure_source(db, _spec(key="directory-owner"))
    second = persist.ensure_source(db, _spec(key="historical-charges"))
    one = persist.store_document(db, first, SourceDoc(url="https://example.org/directory", content=b"directory"), persist.Counters())
    two = persist.store_document(db, second, SourceDoc(url="https://example.org/charges", content=b"charges"), persist.Counters())
    candidate = _institution(identifiers={"ipeds_unitid": "100654"})
    university, _ = persist.upsert_institution(db, candidate, persist.InstitutionResolver(db), source=first, source_document=one)
    corroboration = _institution(identifiers={"ipeds_unitid": "100654"})
    same, _ = persist.upsert_institution(db, corroboration, persist.InstitutionResolver(db), source=second, source_document=two)
    assert university.id == same.id
    claims = db.scalars(select(InstitutionIdentifier).where(InstitutionIdentifier.university_id == university.id)).all()
    assert len(claims) == 1 and claims[0].source_id == first.id
    assert not _source_institution_link(db, university.id, second.id, "historical-charges")
    for fact in corroboration.facts:
        persist.record_fact(db, entity_type="university", entity_id=university.id,
                            source=second, document=two, fact=fact, counters=persist.Counters())
    db.flush()
    assert _source_institution_link(db, university.id, second.id, "historical-charges")
    two.http_status = 404
    db.flush()
    assert not _source_institution_link(db, university.id, second.id, "historical-charges")
