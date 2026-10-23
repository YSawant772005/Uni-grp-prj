"""Global references are idempotent, resumable and isolated from academic approval."""
import io
import json
import sqlite3

import pytest
from sqlalchemy import func, select

from app.ingestion.ror_dump import CONCEPT, artifact, file_hash, json_records, normalized_record, prepare
from app.ingestion.ror_directory import import_directory, plan, protected_fingerprint, reconcile
from app.models import DirectoryInstitution, DirectoryRelease, IngestionJob, InstitutionIdentifier, Source, University


def record(n, **changes):
    value = {'id': f'https://ror.org/0{n:06d}00', 'status': 'active', 'types': ['education'],
        'names': [{'value': f'Test University {n}', 'types': ['ror_display', 'label'], 'lang': 'en'}],
        'locations': [{'geonames_details': {'country_code': 'DE' if n % 2 else 'FR'}}],
        'links': [{'type': 'website', 'value': f'https://university{n}.example'}], 'external_ids': []}
    value.update(changes)
    return value


def staged(tmp_path, rows):
    import zipfile
    root = tmp_path / str(len(list(tmp_path.iterdir())))
    root.mkdir()
    path = root / 'v2.15-2026-10-20-ror-data.zip'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('v2.15-2026-10-20-ror-data.json', json.dumps(rows, ensure_ascii=False))
    metadata = {'id': 999999, 'doi': '10.5281/zenodo.999999', 'conceptdoi': CONCEPT,
        'metadata': {'access_right': 'open', 'publication_date': '2026-10-20', 'license': {'id': 'cc-zero'},
            'creators': [{'name': 'Research Organization Registry'}]},
        'files': [{'key': path.name, 'size': path.stat().st_size, 'checksum': 'md5:' + file_hash(path, 'md5'),
                   'links': {'self': f'https://zenodo.org/api/records/999999/files/{path.name}/content'}}]}
    output = root / 'directory.sqlite'
    manifest = prepare(path, metadata, output)
    return output, manifest


@pytest.mark.parametrize('count', [100, 500])
def test_scale_idempotence_pagination_and_public_isolation(db, client, tmp_path, count):
    path, manifest = staged(tmp_path, [record(n) for n in range(count)])
    before = protected_fingerprint(db)
    approved = plan(db, path, batch_size=73)
    first = import_directory(db, path, approved, approved['confirmation_sha256'])
    assert first['status'] == 'succeeded' and first['created'] == count
    assert protected_fingerprint(db) == before
    second = import_directory(db, path, approved, approved['confirmation_sha256'])
    assert second['created'] == 0 and second['unchanged'] == count
    assert db.scalar(select(func.count()).select_from(DirectoryInstitution)) == count
    assert client.get('/api/v1/programs').json()['total_items'] == 9  # unchanged demo catalogue
    page = client.get('/api/v1/directory/institutions?page_size=17&page=2').json()
    assert page['total_items'] == count and len(page['items']) == 17
    assert all(p['record_status'] == 'unreviewed_reference' and p['masters_availability'] == 'not_assessed' for p in page['items'])
    assert all(p['website']['status'] == 'candidate' for p in page['items'])
    assert client.get('/api/v1/directory/institutions?country=DE').json()['total_items'] == count//2
    assert client.get('/api/v1/directory/institutions?q=Test%20University%201').json()['total_items'] > 0
    assert client.get('/api/v1/directory/institutions?q=%25').json()['total_items'] == 0
    assert client.get('/api/v1/directory/institutions?page_size=101').status_code == 422
    assert client.get('/api/v1/admin/directory/reconciliation').status_code == 401


def test_interrupted_batch_resume_does_not_duplicate_or_publish_partial_release(db, client, tmp_path):
    path, _ = staged(tmp_path, [record(n) for n in range(105)])
    approved = plan(db, path, batch_size=20)
    with pytest.raises(RuntimeError, match='Injected interruption'):
        import_directory(db, path, approved, approved['confirmation_sha256'], fail_after=1)
    job = db.scalar(select(IngestionJob).where(IngestionJob.worker_version == 'ror-directory-bulk-1'))
    assert job.status == 'failed' and job.records_seen == 20
    assert client.get('/api/v1/directory/institutions').json()['total_items'] == 0
    resumed = import_directory(db, path, approved, approved['confirmation_sha256'], resume_job=job.id)
    assert resumed['created'] == resumed['seen'] == 105
    assert db.scalar(select(func.count()).select_from(DirectoryInstitution)) == 105


def test_duplicates_conflicts_education_filter_unicode_and_missing_website(db, client, tmp_path):
    a = record(1)
    b = record(2, names=[{'value': '大学・École', 'types': ['ror_display']}], links=[])
    path, manifest = staged(tmp_path, [a, a, record(1, names=[{'value': 'Conflicting name', 'types': ['ror_display']}]),
        b, record(3, types=['healthcare']), record(4, status='inactive')])
    assert manifest['stats']['duplicate_identifiers'] == 2
    assert manifest['stats']['conflicting_identifiers'] == 1
    assert manifest['stats']['excluded_non_active_education'] == 2
    approved = plan(db, path)
    import_directory(db, path, approved, approved['confirmation_sha256'])
    result = client.get('/api/v1/directory/institutions?q=大学').json()
    assert result['total_items'] == 1 and result['items'][0]['website']['url'] is None
    assert client.get('/api/v1/directory/stats').json()['records'] == 1  # conflict quarantined


def test_strong_conflicts_and_similar_names_never_merge(db, tmp_path):
    university = db.scalar(select(University))
    other = db.scalars(select(University).where(University.id != university.id)).first()
    university.external_identifiers = {**(university.external_identifiers or {}), 'ror': '000000100'}
    db.add(InstitutionIdentifier(university_id=other.id, source_key='fixture', namespace='ror',
        identifier_value='000000100', normalized_value='000000100', scope='institution', claim_status='accepted'))
    db.commit()
    path, _ = staged(tmp_path, [record(1)])
    approved = plan(db, path)
    assert approved['expected_matches']['active_identifier_conflict'] == 1
    before = protected_fingerprint(db)
    import_directory(db, path, approved, approved['confirmation_sha256'])
    assert protected_fingerprint(db) == before


@pytest.mark.parametrize('text', ['[{},]', '[{}]garbage', '[{}', '{}', '[{},{}] x'])
def test_streaming_parser_rejects_corrupt_input(text):
    with pytest.raises(ValueError):
        list(json_records(io.StringIO(text)))


def test_preflight_refuses_changes_or_wrong_confirmation(db, tmp_path):
    path, _ = staged(tmp_path, [record(1)])
    approved = plan(db, path)
    with pytest.raises(ValueError, match='confirmation'):
        import_directory(db, path, approved, 'wrong')
    university = db.scalar(select(University))
    university.canonical_name += ' changed after planning'
    db.commit()
    with pytest.raises(ValueError, match='changed since plan'):
        import_directory(db, path, approved, approved['confirmation_sha256'])
    assert db.scalar(select(func.count()).select_from(DirectoryRelease)) == 0


def test_source_disable_is_enforced_on_repeat_import(db, tmp_path):
    path, _ = staged(tmp_path, [record(1)])
    approved = plan(db, path)
    import_directory(db, path, approved, approved['confirmation_sha256'])
    source = db.scalar(select(Source).where(Source.metadata_json['adapter_key'].astext == 'ror'))
    source.enabled = False
    db.commit()
    with pytest.raises(ValueError, match='disabled'):
        import_directory(db, path, approved, approved['confirmation_sha256'])


def test_same_name_different_country_and_archived_identity_are_only_hints(db, tmp_path):
    import uuid
    from app.db.catalogue_reset import digest
    from app.models import CatalogueArchiveRecord, CatalogueResetOperation
    university = db.scalar(select(University))
    names = [{'value': university.canonical_name, 'types': ['ror_display']}]
    operation = CatalogueResetOperation(id=uuid.uuid4(), operator='Test fixture', reason='Historical fixture',
        original_revision='85b2e4a6c910', backup_path='/test-only', backup_sha256='a'*64, manifest={})
    db.add(operation)
    db.flush()
    archived_id = str(uuid.uuid4())
    payload = {'id': archived_id, 'external_identifiers': {'ror': '000000300'}}
    db.add(CatalogueArchiveRecord(operation_id=operation.id, table_name='universities',
        record_key=archived_id, payload=payload, row_sha256=digest(payload)))
    db.commit()
    path, _ = staged(tmp_path, [
        record(1, names=names, locations=[{'geonames_details': {'country_code': university.country_code}}]),
        record(2, names=names, locations=[{'geonames_details': {'country_code': 'ZZ'}}]), record(3)])
    approved = plan(db, path)
    assert approved['expected_matches'] == {'similar_name_review': 1, 'reference_only': 1, 'archived_identity_review': 1}
    before = protected_fingerprint(db)
    import_directory(db, path, approved, approved['confirmation_sha256'])
    assert protected_fingerprint(db) == before
    historical = db.get(DirectoryInstitution, (approved['artifact']['zip_sha256'], '000000300'))
    assert historical.reconciliation['archived_university_ids'] == [archived_id]
    assert historical.reconciliation['active_university_ids'] == []


def test_failed_batch_rolls_back_rows_and_checkpoint_together(db, tmp_path):
    from sqlalchemy import event
    path, _ = staged(tmp_path, [record(n) for n in range(100)])
    approved = plan(db, path, batch_size=50)
    def fail_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('INSERT INTO directory_institutions'):
            raise RuntimeError('injected write failure')
    engine = db.get_bind()
    event.listen(engine, 'before_cursor_execute', fail_insert)
    try:
        with pytest.raises(RuntimeError, match='injected write failure'):
            import_directory(db, path, approved, approved['confirmation_sha256'])
    finally:
        event.remove(engine, 'before_cursor_execute', fail_insert)
    job = db.scalar(select(IngestionJob).where(IngestionJob.worker_version == 'ror-directory-bulk-1'))
    assert job.status == 'failed' and job.checkpoint['next_ordinal'] == 0
    assert job.records_created == job.records_seen == 0
    assert db.scalar(select(func.count()).select_from(DirectoryInstitution)) == 0
    assert import_directory(db, path, approved, approved['confirmation_sha256'], resume_job=job.id)['created'] == 100


def test_partial_new_release_keeps_previous_complete_release_visible(db, client, tmp_path):
    first, _ = staged(tmp_path, [record(1)])
    approved = plan(db, first)
    import_directory(db, first, approved, approved['confirmation_sha256'])
    second, _ = staged(tmp_path, [record(n) for n in range(5)])
    approved = plan(db, second, batch_size=2)
    partial = import_directory(db, second, approved, approved['confirmation_sha256'], max_batches=1)
    assert partial['status'] == 'partial'
    assert client.get('/api/v1/directory/institutions').json()['total_items'] == 1
    import_directory(db, second, approved, approved['confirmation_sha256'], resume_job=partial['job_id'])
    assert client.get('/api/v1/directory/institutions').json()['total_items'] == 5


def test_review_queue_access_and_public_provenance_do_not_expose_local_paths(db, client, make_user, tmp_path):
    from app.core.security import create_access_token
    student, reviewer = make_user('student'), make_user('reviewer')
    db.commit()
    path, _ = staged(tmp_path, [record(1)])
    approved = plan(db, path)
    import_directory(db, path, approved, approved['confirmation_sha256'])
    endpoint = '/api/v1/admin/directory/reconciliation'
    assert client.get(endpoint, headers={'Authorization': 'Bearer '+create_access_token(str(student.id), ['student'])}).status_code == 403
    response = client.get(endpoint, headers={'Authorization': 'Bearer '+create_access_token(str(reviewer.id), ['reviewer'])})
    assert response.status_code == 200 and response.json()['total_items'] == 0
    assert 'zip_path' not in client.get('/api/v1/directory/stats').json()['source']


def test_malformed_website_is_missing_not_a_rejected_institution():
    value = normalized_record(record(1, links=[{'type': 'website', 'value': 'https://[broken'}]), 1)
    assert value['website_candidate'] is None and value['name'] == 'Test University 1'


def test_directory_jobs_cannot_be_retried_or_claimed_as_catalogue_ingestion(db, client, make_user, tmp_path):
    from app.core.security import create_access_token
    from app.ingestion.pipeline import _claim_job
    from app.core.scheduler import drain_queued_jobs
    actor = make_user('admin')
    db.commit()
    path, _ = staged(tmp_path, [record(n) for n in range(5)])
    approved = plan(db, path, batch_size=2)
    with pytest.raises(RuntimeError, match='Injected interruption'):
        import_directory(db, path, approved, approved['confirmation_sha256'], fail_after=1)
    job = db.scalar(select(IngestionJob).where(IngestionJob.worker_version == 'ror-directory-bulk-1'))
    headers = {'Authorization': 'Bearer '+create_access_token(str(actor.id), ['admin'])}
    detail = client.get(f'/api/v1/admin/jobs/{job.id}', headers=headers).json()
    assert detail['metrics']['directory_records']['created'] == 2
    assert detail['metrics']['institutions']['created'] == detail['metrics']['programs']['created'] == 0
    response = client.post(f'/api/v1/admin/jobs/{job.id}/retry', headers=headers)
    assert response.status_code == 409 and response.json()['error']['code'] == 'DIRECTORY_RESUME_REQUIRED'
    db.refresh(job)
    assert job.status == 'failed' and job.checkpoint['next_ordinal'] == 2
    with pytest.raises(ValueError, match='approved bulk import plan'):
        _claim_job(db, job.id, db.get(Source, job.source_id), actor.id)
    # Defensive dispatch isolation even if an operator incorrectly queues this job.
    job.status = 'queued'
    db.commit()
    assert drain_queued_jobs() == 0
    db.refresh(job)
    assert job.status == 'queued' and job.worker_version == 'ror-directory-bulk-1'


@pytest.mark.parametrize('defect', ['checksum', 'licence', 'host', 'concept'])
def test_untrusted_release_rejected_before_staging(tmp_path, defect):
    path, _ = staged(tmp_path, [record(1)])
    zip_path = path.parent / 'v2.15-2026-10-20-ror-data.zip'
    metadata = {'conceptdoi': CONCEPT, 'metadata': {'access_right': 'open', 'publication_date': '2026-10-20',
        'license': {'id': 'cc-zero'}, 'creators': [{'name': 'Research Organization Registry'}]},
        'files': [{'key': zip_path.name, 'size': zip_path.stat().st_size, 'checksum': 'md5:'+file_hash(zip_path, 'md5'),
                   'links': {'self': 'https://zenodo.org/file'}}]}
    if defect == 'checksum':
        metadata['files'][0]['checksum'] = 'md5:'+'0'*32
    elif defect == 'licence':
        metadata['metadata']['license']['id'] = 'all-rights-reserved'
    elif defect == 'host':
        metadata['files'][0]['links']['self'] = 'https://untrusted.example/file'
    else:
        metadata['conceptdoi'] = '10.1234/unrelated'
    output = path.parent / 'refused.sqlite'
    with pytest.raises(ValueError):
        prepare(zip_path, metadata, output)
    assert not output.exists()
