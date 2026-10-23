"""Official-format fixtures: raw passages stay private until human summary review."""
import pytest
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.core.security import create_access_token
from app.ingestion.pipeline import RunOptions, run_source
from app.models import FactEvidence, FactRecord, FactVersion, InstitutionReview, Program, ProgramIdentifier, Source, SourceDocument
from app.services import admin, catalog
from test_ual_program_pages import batch, html, make_fetcher, page_url, patch_pipeline, setup_ual  # noqa: F401


PASSAGE = ('The course examines public communication across several disciplines. '
    'Students explore how organisations and individuals exchange ideas through media and social settings. '
    'Teaching brings together perspectives that support the study of communication practices and research.')
SUMMARY = 'An interdisciplinary programme examining media, interpersonal communication and approaches to communication research.'
SCOPE = 'col-sm-12 col-md-8 col-lg-8'


def described(markup=None):
    body = markup if markup is not None else f'<p>{PASSAGE}</p>'
    return html('7101').replace('</body>', f'<div class="row"><div class="{SCOPE}">{body}</div></div></body>')


def description_fact(result):
    return [fact for p in result.institutions[0].programs for d in p.documents for fact in d.facts
            if fact.fact_key == 'program_description']


def test_presentation_prose_is_a_bounded_candidate_with_same_page_provenance(make_fetcher):
    fetcher = make_fetcher({page_url('7101'): described(
        f'<nav><p>Navigation text that must never become a description even when it is lengthy enough.</p></nav>'
        f'<p>{PASSAGE}</p><p hidden>Hidden text that must never be included in the reference passage.</p>')})
    result = batch(fetcher)
    facts = description_fact(result)
    assert len(facts) == 1
    fact = facts[0]
    assert fact.status == 'candidate' and fact.value['summary'] is None
    assert fact.value['source_excerpt'] == PASSAGE
    assert fact.value['plan_code'] == '7101'
    assert fact.value['reuse_basis'] == 'reference_excerpt_for_review'
    assert len(fact.value['source_excerpt'].split()) <= 80
    assert len(fact.value['source_excerpt']) <= 800
    assert PASSAGE in fact.excerpt and 'Navigation' not in fact.excerpt and 'Hidden' not in fact.excerpt
    assert 'program_description' not in {f.fact_key for f in result.institutions[0].programs[0].facts}
    assert fetcher.calls.count(page_url('7101')) == 1  # no request amplification


@pytest.mark.parametrize('body', ['', '<p> </p>', '<p>{{pre.description}}</p>',
    '<p>{{pre.presentacion[0].n_creditos}} Credits and other unresolved content that is not real academic information.</p>',
    '<nav><p>This navigation paragraph contains a lot of words but no programme description at all.</p></nav>',
    '<div class="avisos"><p>A generic notice about university guides is not a programme description for students.</p></div>',
    '<p style="display:none">An invisible programme placeholder must not be treated as real page evidence.</p>'])
def test_empty_template_hidden_and_boilerplate_descriptions_are_ignored(make_fetcher, body):
    assert not description_fact(batch(make_fetcher({page_url('7101'): described(body)})))


@pytest.mark.parametrize('markup', [html('7112'), html('7101', 'Master in Unrelated Chemistry'),
                                   '<html><h1>Welcome to the university</h1></html>'])
def test_wrong_plan_wrong_title_and_generic_200_never_create_descriptions(make_fetcher, markup):
    assert not description_fact(batch(make_fetcher({page_url('7101'): markup})))


def _ingest(db, monkeypatch, make_fetcher):
    university, _, _ = setup_ual(db)
    patch_pipeline(monkeypatch, make_fetcher, {page_url('7101'): described()})
    result = run_source('ual_masters', RunOptions(max_records=5), db=db)
    assert result.status == 'succeeded', result.error
    claim = db.scalar(select(ProgramIdentifier).where(ProgramIdentifier.external_key == 'ual:master:plan:7101'))
    program = db.get(Program, claim.program_id)
    fact = db.scalar(select(FactRecord).where(FactRecord.entity_id == program.id, FactRecord.fact_key == 'program_description'))
    return university, program, fact, db.get(FactVersion, fact.current_version_id)


def test_description_review_appends_version_preserves_evidence_and_never_publishes_other_programs(
        db, monkeypatch, make_fetcher, make_user, client):
    university, program, fact, original = _ingest(db, monkeypatch, make_fetcher)
    reviewer = make_user('reviewer')
    ids = set(db.scalars(select(Program.id).where(Program.university_id == university.id)))
    review = db.scalar(select(InstitutionReview).where(InstitutionReview.university_id == university.id))
    review.status = 'approved'  # isolated fixture of the completed pilot
    db.commit()
    assert client.get('/api/v1/programs?country=ES').json()['total_items'] == 0
    evidence = db.scalar(select(FactEvidence).where(FactEvidence.fact_version_id == original.id))
    document = db.get(SourceDocument, evidence.source_document_id)
    assert document.canonical_url == page_url('7101') and document.content_hash
    assert PASSAGE in evidence.evidence_excerpt
    assert program.description is None
    # Simulate the pilot's independent URL reviews and one publication decision.
    for p in db.scalars(select(Program).where(Program.id.in_(ids))):
        url_fact = db.scalar(select(FactRecord).where(FactRecord.entity_id == p.id, FactRecord.fact_key == 'official_program_page_url'))
        admin.approve_fact(db, reviewer, url_fact.id, None, 'Official plan and title evidence support this page.', None)
    program.publication_status = 'published'
    db.commit()
    assert client.get(f'/api/v1/programs/{program.id}').json()['description'] is None
    assert all(i['fact_key'] != 'program_description' for i in client.get(
        f'/api/v1/programs/{program.id}/evidence?page_size=100').json()['items'])
    assert client.post(f'/api/v1/admin/facts/{fact.id}/approve', json={'description_summary': SUMMARY}).status_code == 401
    headers = {'Authorization': 'Bearer ' + create_access_token(str(reviewer.id), ['reviewer'])}
    response = client.post(f'/api/v1/admin/facts/{fact.id}/approve', headers=headers,
        json={'version_id': str(original.id), 'description_summary': SUMMARY,
              'reason': 'The official presentation passage supports this independently written programme summary.'})
    assert response.status_code == 200, response.text
    assert response.json()['projection_status'] == 'applied'
    db.expire_all()
    current = db.get(FactVersion, db.get(FactRecord, fact.id).current_version_id)
    assert current.id != original.id and current.version_number == 2
    assert db.get(FactVersion, original.id).value_json['summary'] is None
    assert current.extraction_method == 'reviewer_summary' and current.status == 'verified'
    copied = db.scalar(select(FactEvidence).where(FactEvidence.fact_version_id == current.id))
    assert copied.id != evidence.id and copied.source_document_id == document.id
    assert copied.evidence_excerpt == evidence.evidence_excerpt
    detail = client.get(f'/api/v1/programs/{program.id}').json()
    assert detail['description'] == SUMMARY and PASSAGE not in str(detail)
    assert detail['description_source']['source_url'] == page_url('7101')
    assert detail['description_source']['retrieved_at'] and detail['description_source']['verified_at']
    assert detail['academic_completeness']['status'] == 'limited'
    before = tuple(db.scalar(select(func.count()).select_from(m)) for m in (FactRecord, FactVersion, FactEvidence))
    repeated = run_source('ual_masters', RunOptions(max_records=5), db=db)
    assert repeated.status == 'succeeded' and repeated.counters.review == repeated.counters.created == 0
    assert tuple(db.scalar(select(func.count()).select_from(m)) for m in (FactRecord, FactVersion, FactEvidence)) == before
    assert db.get(Program, program.id).description == SUMMARY
    assert set(db.scalars(select(Program.id).where(Program.university_id == university.id))) == ids
    assert db.scalar(select(func.count()).select_from(Program).where(Program.id.in_(ids), Program.publication_status == 'published')) == 1
    assert db.scalar(select(func.count()).select_from(Program).where(Program.id.in_(ids), Program.publication_status == 'candidate')) == 4
    # Withdrawal removes the public projection while preserving stored history.
    admin.reject_fact(db, reviewer, fact.id, current.id, 'The source summary requires further evidence review.', None)
    db.commit()
    assert db.get(Program, program.id).description == SUMMARY
    assert client.get(f'/api/v1/programs/{program.id}').json()['description'] is None


@pytest.mark.parametrize('damage', ['wrong_plan', 'wrong_title', 'wrong_url', 'failed', 'conflict', 'restricted', 'wrong_source'])
def test_description_projection_requires_matching_official_page_evidence(db, monkeypatch, make_fetcher, make_user, damage):
    _, program, fact, version = _ingest(db, monkeypatch, make_fetcher)
    evidence = db.scalar(select(FactEvidence).where(FactEvidence.fact_version_id == version.id))
    document = db.get(SourceDocument, evidence.source_document_id)
    if damage in {'wrong_plan', 'wrong_title', 'wrong_url'}:
        key, value = {'wrong_plan': ('plan_code', '7112'), 'wrong_title': ('page_title', 'Other degree'),
                      'wrong_url': ('url', page_url('7112'))}[damage]
        version.value_json = {**version.value_json, key: value}
    elif damage == 'failed':
        document.http_status = 503
    elif damage == 'conflict':
        evidence.supports_or_conflicts = 'conflicts'
    elif damage == 'restricted':
        db.get(Source, document.source_id).allowed_use_policy = 'review_required'
    else:
        db.get(Source, document.source_id).source_type = 'licensed_aggregator'
    db.flush()
    with pytest.raises(ApiError), db.begin_nested():
        admin.approve_fact(db, make_user('reviewer'), fact.id, version.id,
            'Official source evidence must support this description.', None, description_summary=SUMMARY)
    assert program.description is None and fact.current_status == 'candidate'


@pytest.mark.parametrize('summary', [None, '', '{{pre.description}}', '<p>Copied markup is not a valid public description.</p>',
                                   PASSAGE, 'x' * 601])
def test_summary_must_be_explicit_plain_text_and_independently_written(db, monkeypatch, make_fetcher, make_user, summary):
    _, program, fact, version = _ingest(db, monkeypatch, make_fetcher)
    with pytest.raises(ApiError), db.begin_nested():
        admin.approve_fact(db, make_user('reviewer'), fact.id, version.id,
            'The official source is reviewed for a written summary.', None, description_summary=summary)
    assert program.description is None


def test_existing_authored_description_is_preserved(db, monkeypatch, make_fetcher, make_user):
    _, program, fact, version = _ingest(db, monkeypatch, make_fetcher)
    program.description = 'Existing independently authored programme description.'
    db.flush()
    with pytest.raises(ApiError, match='preserved'), db.begin_nested():
        admin.approve_fact(db, make_user('reviewer'), fact.id, version.id,
            'Official evidence supports this description summary.', None, description_summary=SUMMARY)
    assert program.description == 'Existing independently authored programme description.'
    from app.services.program_descriptions import public_description
    assert public_description(db, program) == (program.description, None)
