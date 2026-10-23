"""UAL page integration uses deterministic official-format fixtures, never live HTTP."""
import json
import uuid

import httpx
import pytest
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.ingestion.adapters.base import RunContext
from app.ingestion.adapters.ual import API, CATALOGUE, UalMastersAdapter
from app.ingestion.http import Fetcher
from app.ingestion.normalize import normalize_url
from app.ingestion.pipeline import RunOptions, run_source
from app.ingestion import persist
from app.ingestion.registry import get_spec
from app.models import (
    CatalogueResetOperation, FactEvidence, FactRecord, FactVersion, InstitutionIdentifier,
    InstitutionIdentityReview, InstitutionReview, Program, ProgramIdentifier,
    SourceDocument, SourceDocumentRetrieval, University,
)
from app.services import admin, catalog
from app.services.program_evidence import official_program_page, public_program_page_url

TITLES = {
    '7101': 'Máster en Comunicación Social',
    '7133': 'Máster en Enseñanza de la Lengua y la Literatura Española Profesorado ELE',
    '7112': 'Máster en Estudios Avanzados en Historia: el Mundo Mediterráneo Occidental',
    '7138': 'Máster en Estudios Ingleses Avanzados',
    '7150': 'Máster en Estudios sobre Mujeres, Feminismos y Género en Humanidades',
}
PAGE_TITLES = {**TITLES,
    '7133': 'Máster en Enseñanza de la Lengua y la Literatura Españolas para Profesorado de Español como Lengua Extranjera',
    '7150': 'Máster en Estudios s/ Mujeres, Feminismos y Género p la inv. en Humanidades',
}
ROBOTS = 'https://www.ual.es/robots.txt'
LINKS = '<a href="/estudios/masteres/presentacion/{{t.cod_plan}}"><span>{{t.nom_plan}}</span></a>'


def page_url(code):
    return 'https://www.ual.es/estudios/masteres/presentacion/' + code


def html(code, title=None):
    return f'''<html><head><title>Presentación - Universidad de Almería</title></head>
    <body><h1 id="tituloGrado"></h1>
    <script>var parameters = ['{code}'];
    $('head').append('<meta name="description" content="{title or PAGE_TITLES[code]} de la Universidad de Almería">');</script>
    <dl><dt>Créditos</dt><dd>{{{{pre.presentacion[0].n_creditos}}}}</dd>
    <dt>Tuition</dt><dd>{{{{pre.tuition}}}}</dd></dl></body></html>'''


@pytest.fixture
def make_fetcher():
    clients = []

    def make(overrides=None, rows=None):
        data = {API: {'planes': rows or [dict(cod_plan=c, nom_plan=t, cod_rama='1',
            nom_rama='Artes y Humanidades', interuni_sn='N', l_doble_sn='N',
            d_tip_ensenanza='Presencial') for c, t in TITLES.items()]},
            ROBOTS: 'User-agent: *\nAllow: /', CATALOGUE: LINKS,
            **{page_url(c): html(c) for c in TITLES}}
        data.update(overrides or {})
        calls = []

        def handler(request):
            url = str(request.url)
            calls.append(url)
            assert url in data, f'unexpected crawl: {url}'
            value = data[url]
            if isinstance(value, list):
                value = value.pop(0)
            if isinstance(value, Exception):
                raise value
            if isinstance(value, httpx.Response):
                return value
            if isinstance(value, dict):
                return httpx.Response(200, json=value)
            return httpx.Response(200, text=value, headers={'Content-Type': 'text/html; charset=utf-8'})

        fetcher = Fetcher(user_agent='UniShortlist/test', rps=0, backoff=0, max_retries=2, timeout=1)
        fetcher._client.close()
        fetcher._client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        fetcher.calls = calls
        clients.append(fetcher)
        return fetcher

    yield make
    for client in clients:
        client.close()


def batch(fetcher, limit=5, **options):
    return next(UalMastersAdapter().iter_batches(RunContext(fetcher=fetcher, max_records=limit, **options)))


@pytest.mark.parametrize('code', TITLES)
def test_all_five_official_pages_become_candidates_not_verified_values(make_fetcher, code):
    fetcher = make_fetcher()
    result = batch(fetcher)
    assert not result.warnings
    program = next(p for p in result.institutions[0].programs if p.external_key.endswith(':' + code))
    discovery, page = program.documents
    assert discovery.document.url == CATALOGUE
    assert '{{t.cod_plan}}' in discovery.facts[0].excerpt
    assert page.document.url == page_url(code) and page.document.http_status == 200
    assert page.document.content == html(code).encode()
    fact = page.facts[0]
    assert fact.fact_key == 'official_program_page_url' and fact.status == 'candidate'
    assert fact.value['source_program_key'] == f'ual:master:plan:{code}'
    assert fact.value['plan_code'] == code and PAGE_TITLES[code] in fact.excerpt
    assert program.official_url is None  # relational URL requires explicit review
    assert {f.fact_key for d in program.documents for f in d.facts} == {
        'official_program_page_discovery', 'official_program_page_url'}
    assert len(fetcher.calls) == 8  # API, robots once, catalogue once, five pages


@pytest.mark.parametrize('bad_page', [
    '<html><h1>Universidad de Almería</h1></html>',
    '<meta name="description" content><script>var parameters = ["7101"];</script>',
    html('7101', 'Máster en Física Nuclear'),
    html('7112', TITLES['7101']),
    html('7101', '{{nom.dsplan}}'),
    '<h1>Máster en Comunicación Social</h1>',  # no plan binding
])
def test_wrong_titles_generic_200_and_wrong_or_missing_plan_are_rejected(make_fetcher, bad_page):
    result = batch(make_fetcher({page_url('7101'): bad_page}))
    assert not result.institutions[0].programs[0].documents
    assert any('7101' in warning for warning in result.warnings)
    assert all(p.documents for p in result.institutions[0].programs[1:])


@pytest.mark.parametrize('destination', ['https://unrelated.example/course/7101',
                                      'https://www.ual.es/', page_url('7112')])
def test_redirects_to_unrelated_or_generic_or_other_plan_are_not_followed(make_fetcher, destination):
    fetcher = make_fetcher({page_url('7101'): httpx.Response(302, headers={'Location': destination})})
    result = batch(fetcher, limit=1)
    assert not result.institutions[0].programs[0].documents
    assert destination not in fetcher.calls


def test_same_plan_official_redirect_is_checked_and_actual_url_retained(make_fetcher):
    alternate = page_url('7101') + '?idioma=es_ES'
    fetcher = make_fetcher({page_url('7101'): httpx.Response(302, headers={'Location': alternate}),
                            alternate: html('7101')})
    result = batch(fetcher, limit=1)
    assert result.institutions[0].programs[0].documents[-1].document.url == alternate


@pytest.mark.parametrize('markup', [
    html('7101', 'MASTER EN COMUNICACION SOCIAL'),
    '<h1>Master’s Degree in Social Communication</h1>' + html('7101'),
])
def test_accents_and_published_bilingual_title_evidence_are_supported(make_fetcher, markup):
    assert batch(make_fetcher({page_url('7101'): markup}), limit=1).institutions[0].programs[0].documents


def test_translation_is_not_invented_without_a_source_backed_matching_title(make_fetcher):
    result = batch(make_fetcher({page_url('7101'): html('7101', 'Master in Mathematics')}), limit=1)
    assert not result.institutions[0].programs[0].documents


def test_no_program_url_is_guessed_without_published_links(make_fetcher):
    fetcher = make_fetcher({CATALOGUE: '<h1>Másteres oficiales</h1>'})
    result = batch(fetcher)
    assert not any(p.documents for p in result.institutions[0].programs)
    assert not any('/presentacion/' in url for url in fetcher.calls)


def test_literal_catalogue_link_is_supported(make_fetcher):
    result = batch(make_fetcher({CATALOGUE: '<a href="' + page_url('7101') + '">Comunicación Social</a>'}), limit=1)
    assert result.institutions[0].programs[0].documents


def test_robots_denial_blocks_only_page_enrichment(make_fetcher):
    fetcher = make_fetcher({ROBOTS: 'User-agent: *\nDisallow: /estudios/masteres/presentacion/'})
    result = batch(fetcher)
    assert len(result.institutions[0].programs) == 5
    assert not any(p.documents for p in result.institutions[0].programs)
    assert not any('/presentacion/' in url for url in fetcher.calls)


@pytest.mark.parametrize('response', [httpx.Response(503), httpx.Response(302, headers={'Location': 'https://unrelated.example/robots.txt'})])
def test_unestablished_or_redirected_robots_permission_fails_closed(make_fetcher, response):
    fetcher = make_fetcher({ROBOTS: response})
    result = batch(fetcher)
    assert not any(p.documents for p in result.institutions[0].programs)
    assert CATALOGUE not in fetcher.calls


def test_explicit_robots_404_allows_public_pages(make_fetcher):
    assert not batch(make_fetcher({ROBOTS: httpx.Response(404)})).warnings


def test_transient_failure_retries_and_eventually_records_candidate(make_fetcher):
    fetcher = make_fetcher({page_url('7101'): [httpx.ConnectError('temporary'), html('7101')]})
    result = batch(fetcher, limit=1)
    assert result.institutions[0].programs[0].documents
    assert fetcher.calls.count(page_url('7101')) == 2
    assert result.institutions[0].programs[0].documents[-1].document.retrieval_attempt_count == 2


@pytest.mark.parametrize('error', [httpx.Response(404), httpx.Response(503), httpx.ConnectError('unavailable')])
def test_failed_page_keeps_catalogue_and_other_pages_without_fabricated_evidence(make_fetcher, error):
    result = batch(make_fetcher({page_url('7101'): error}))
    assert result.warnings and not result.institutions[0].programs[0].documents
    assert all(p.documents for p in result.institutions[0].programs[1:])


def test_unresolved_templates_never_become_academic_values(make_fetcher):
    result = batch(make_fetcher())
    for program in result.institutions[0].programs:
        facts = program.facts + [f for d in program.documents for f in d.facts]
        assert not {f.fact_key for f in facts} & {'duration', 'ects', 'tuition', 'admission_requirement', 'intake_dates'}
        assert program.duration_min_months is program.duration_max_months is None


def test_page_budget_and_offline_mode_are_bounded(make_fetcher):
    rows = [dict(cod_plan=str(7100+i), nom_plan='Máster en Comunicación Social',
                 interuni_sn='N', l_doble_sn='N') for i in range(20)]
    fetcher = make_fetcher(rows=rows)
    result = batch(fetcher, limit=20, offline=True)
    assert len(result.institutions[0].programs) == 20
    assert fetcher.calls == [API]
    fetcher = make_fetcher({**{page_url(str(7100+i)): html('7101').replace('7101',str(7100+i)) for i in range(5)}}, rows=rows)
    result = batch(fetcher, limit=20)
    assert len([u for u in fetcher.calls if '/presentacion/' in u]) == 5
    assert any('capped' in w for w in result.warnings)


def setup_ual(db):
    source = persist.ensure_source(db, get_spec('ual_masters'))
    persist.ensure_country(db, 'ES', 'Spain')
    university = University(canonical_name='Universidad de Almería', slug='ual-page-test',
        country_code='ES', official_website_url='https://www.ual.es', external_identifiers={})
    db.add(university)
    document = persist.store_document(db, source, persist.SourceDoc(url=API, content=b'identity'), persist.Counters())
    db.flush()
    review = InstitutionIdentityReview(source_id=source.id, source_document_id=document.id,
        external_key='ual:publisher:u04800001', candidate_payload={}, status='approved', resolved_university_id=university.id)
    db.add(review)
    db.commit()
    return university, source, review


def patch_pipeline(monkeypatch, make_fetcher, overrides=None):
    monkeypatch.setattr('app.ingestion.pipeline.Fetcher', lambda **kwargs: make_fetcher(overrides))


def fact_rows(db, program, key='official_program_page_url'):
    fact = db.scalar(select(FactRecord).where(FactRecord.entity_id == program.id, FactRecord.fact_key == key))
    return fact, db.get(FactVersion, fact.current_version_id)


def test_existing_identities_catalogue_binding_and_repeat_import_are_preserved(db, monkeypatch, make_fetcher):
    university, source, review = setup_ual(db)
    patch_pipeline(monkeypatch, make_fetcher, {ROBOTS: 'User-agent: *\nDisallow: /'})
    first = run_source('ual_masters', RunOptions(max_records=5), db=db)
    assert first.status == 'partial' and first.counters.programs_created == 5
    legacy_repeat = run_source('ual_masters', RunOptions(max_records=5), db=db)
    assert legacy_repeat.counters.unchanged == 20
    assert legacy_repeat.counters.created == legacy_repeat.counters.review == 0
    assert legacy_repeat.counters.programs_unchanged == 5
    ids = set(db.scalars(select(Program.id).where(Program.university_id == university.id)))
    bindings = dict(db.execute(select(ProgramIdentifier.program_id, ProgramIdentifier.source_document_id)
                              .where(ProgramIdentifier.program_id.in_(ids))).all())
    patch_pipeline(monkeypatch, make_fetcher)
    second = run_source('ual_masters', RunOptions(max_records=5), db=db)
    assert second.status == 'succeeded', second.as_dict()
    assert second.counters.programs_created == second.counters.institutions_created == 0
    assert second.counters.created == 10  # two new candidate facts per existing program
    for program in db.scalars(select(Program).where(Program.id.in_(ids))):
        assert program.official_program_url is None and program.publication_status == 'candidate'
        fact, version = fact_rows(db, program)
        evidence = db.scalar(select(FactEvidence).where(FactEvidence.fact_version_id == version.id))
        document = db.get(SourceDocument, evidence.source_document_id)
        assert document.document_type == 'html' and document.canonical_url == version.value_json['url']
        assert document.id != bindings[program.id]
        assert fact.current_status == version.status == 'candidate'
        assert official_program_page(db, program)['status'] == 'unverified_candidate'
        assert public_program_page_url(db, program, university) is None
    before = {m:db.scalar(select(func.count()).select_from(m)) for m in [Program, ProgramIdentifier, FactRecord, FactVersion, FactEvidence, SourceDocument]}
    retrieved = db.scalar(select(func.count()).select_from(SourceDocumentRetrieval))
    third = run_source('ual_masters', RunOptions(max_records=5), db=db)
    assert third.status == 'succeeded', third.as_dict()
    assert third.counters.programs_unchanged == 5 and third.counters.institutions_unchanged == 1
    assert third.counters.created == third.counters.review == third.counters.conflicted == 0
    assert third.counters.unchanged == 30
    assert before == {m:db.scalar(select(func.count()).select_from(m)) for m in before}
    assert db.scalar(select(func.count()).select_from(SourceDocumentRetrieval)) - retrieved == 7
    assert bindings == dict(db.execute(select(ProgramIdentifier.program_id, ProgramIdentifier.source_document_id).where(ProgramIdentifier.program_id.in_(ids))).all())
    assert db.get(InstitutionIdentityReview, review.id).status == 'approved'
    assert db.scalar(select(InstitutionIdentifier.claim_status).where(InstitutionIdentifier.university_id == university.id)) == 'pending_review'
    assert db.scalar(select(InstitutionReview.status).where(InstitutionReview.university_id == university.id)) == 'pending'
    detail = admin.institution_review_detail(db, university.id)
    assert detail['program_coverage']['evidence_backed_program_count'] == 5


@pytest.mark.parametrize('code', TITLES)
def test_only_explicit_fact_review_projects_supported_url_and_does_not_publish(db, monkeypatch, make_fetcher, make_user, code):
    university, _, _ = setup_ual(db)
    patch_pipeline(monkeypatch, make_fetcher)
    assert run_source('ual_masters', RunOptions(max_records=5), db=db).status == 'succeeded'
    claim = db.scalar(select(ProgramIdentifier).where(ProgramIdentifier.external_key == f'ual:master:plan:{code}'))
    program = db.get(Program, claim.program_id)
    fact, version = fact_rows(db, program)
    reviewer = make_user('reviewer')
    assert program.official_program_url is None
    result = admin.approve_fact(db, reviewer, fact.id, version.id, 'The official UAL page and matching plan/title evidence support this URL.', None)
    assert result['projection_status'] == 'applied'
    assert official_program_page(db, program)['status'] == 'verified'
    assert program.official_program_url == normalize_url(page_url(code))
    assert program.publication_status == 'candidate'
    assert not catalog.student_visible_program(db, program)
    assert admin._publication_evidence(db, program)[0] is False  # no institution approval
    reviewed_at = version.reviewed_at
    replay = run_source('ual_masters', RunOptions(max_records=5), db=db)
    assert replay.status == 'succeeded' and replay.counters.review == replay.counters.conflicted == 0
    db.refresh(fact); db.refresh(version)
    assert fact.current_status == version.status == 'verified'
    assert version.reviewed_at == reviewed_at and version.reviewed_by_user_id == reviewer.id
    assert program.publication_status == 'candidate' and official_program_page(db, program)['status'] == 'verified'


@pytest.mark.parametrize('damage', ['missing', 'failed', 'wrong_plan', 'wrong_owner', 'wrong_title', 'catalogue'])
def test_review_rejects_unsupported_url_projection(db, monkeypatch, make_fetcher, make_user, damage):
    _, _, _ = setup_ual(db)
    patch_pipeline(monkeypatch, make_fetcher)
    assert run_source('ual_masters', RunOptions(max_records=1), db=db).status == 'succeeded'
    program = db.scalar(select(Program).join(ProgramIdentifier).where(ProgramIdentifier.external_key == 'ual:master:plan:7101'))
    fact, version = fact_rows(db, program)
    evidence = db.scalar(select(FactEvidence).where(FactEvidence.fact_version_id == version.id))
    if damage == 'missing':
        db.delete(evidence)
    elif damage == 'failed':
        db.get(SourceDocument, evidence.source_document_id).http_status = 404
    else:
        value = dict(version.value_json)
        if damage == 'wrong_plan': value['plan_code'] = '9999'
        elif damage == 'wrong_owner': value['source_program_key'] = 'ual:master:plan:7133'
        elif damage == 'wrong_title': value['page_title'] = 'Máster en Física'
        else: value['url'] = CATALOGUE
        version.value_json = value
    db.flush()
    with pytest.raises(ApiError) as error:
        admin.approve_fact(db, make_user('reviewer'), fact.id, version.id, 'The URL must retain valid official source evidence.', None)
    assert error.value.status_code == 422
    assert program.official_program_url is None and fact.current_status == 'candidate'


def test_dry_run_and_student_visibility_preserve_review_boundaries(db, monkeypatch, make_fetcher, client):
    university, _, _ = setup_ual(db)
    patch_pipeline(monkeypatch, make_fetcher)
    before = {m:db.scalar(select(func.count()).select_from(m)) for m in [Program, FactRecord, SourceDocument]}
    from app.db.catalogue_reset import snapshot
    full_before = snapshot(db.connection())
    summary = run_source('ual_masters', RunOptions(max_records=5, dry_run=True), db=db)
    assert summary.status == 'dry_run', summary.as_dict()
    assert before == {m:db.scalar(select(func.count()).select_from(m)) for m in before}
    assert snapshot(db.connection()) == full_before
    assert run_source('ual_masters', RunOptions(max_records=5), db=db).status == 'succeeded'
    assert client.get('/api/v1/programs?q=Comunicaci').json()['total_items'] == 0
    ids = list(db.scalars(select(Program.id).where(Program.university_id == university.id)))
    assert all(client.get(f'/api/v1/programs/{pid}').status_code == 404 for pid in ids)


def test_admin_api_keeps_candidate_shape_and_requires_reviewer_for_projection(db, monkeypatch, make_fetcher, make_user, client):
    from app.core.security import create_access_token
    university, _, _ = setup_ual(db)
    patch_pipeline(monkeypatch, make_fetcher)
    assert run_source('ual_masters', RunOptions(max_records=1), db=db).status == 'succeeded'
    reviewer, student = make_user('reviewer'), make_user('student')
    db.commit()
    headers = {'Authorization': 'Bearer ' + create_access_token(str(reviewer.id), ['reviewer'])}
    response = client.get(f'/api/v1/admin/institution-reviews/{university.id}', headers=headers)
    assert response.status_code == 200
    item = response.json()['programs'][0]
    assert item['program_page_evidence']['status'] == 'unverified_candidate'
    fact_id = item['program_page_evidence']['fact_id']
    route = f'/api/v1/admin/facts/{fact_id}/approve'
    assert client.post(route, json={}).status_code == 401
    student_headers = {'Authorization': 'Bearer ' + create_access_token(str(student.id), ['student'])}
    assert client.post(route, json={}, headers=student_headers).status_code == 403
    approved = client.post(route, json={'reason':'The official UAL page matches this programme plan and title.'}, headers=headers)
    assert approved.status_code == 200 and approved.json()['projection_status'] == 'applied'
    assert client.get('/api/v1/programs?q=Comunicaci').json()['total_items'] == 0
    item = client.get(f'/api/v1/admin/institution-reviews/{university.id}', headers=headers).json()['programs'][0]
    assert item['program_page_evidence']['status'] == 'verified'
    assert item['publication_status'] == 'candidate'


def test_archived_identity_does_not_override_the_active_decision(db):
    university, source, active = setup_ual(db)
    operation = CatalogueResetOperation(id=uuid.uuid4(), operator='isolated fixture', reason='Historical test context',
        original_revision='85b2e4a6c910', backup_path='/test-only', backup_sha256='a'*64, manifest={})
    db.add(operation);db.flush()
    archived = InstitutionIdentityReview(source_id=source.id, source_document_id=active.source_document_id,
        external_key=active.external_key, candidate_payload={}, status='approved', archived_operation_id=operation.id)
    db.add(archived);db.flush()
    candidate = persist.CandidateInstitution(external_key=active.external_key, name=university.canonical_name,
        country_code='ES', identifiers={'ual_dataset_publisher':'u04800001'})
    assert persist.InstitutionResolver(db).resolve(candidate, source.id) == (university.id, 'reviewed_link')
    active.status, active.resolved_university_id = 'deferred', None
    db.flush()
    assert persist.InstitutionResolver(db).resolve(candidate, source.id)[1] != 'reviewed_link'
    assert archived.status == 'approved' and archived.resolved_university_id is None
