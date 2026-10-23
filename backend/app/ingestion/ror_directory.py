"""Explicitly planned, checkpointed directory-only import. Never creates universities.

python -m app.ingestion.ror_directory --help
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import and_, func, inspect, or_, select, text
from sqlalchemy.dialects.postgresql import insert

from app.ingestion.ror_dump import artifact, file_hash, prepare, stable

WORKER = 'ror-directory-bulk-1'
REVISION = '9c24a7e6d180'
MUTABLE_IMPORT_TABLES = {'directory_releases', 'directory_institutions', 'sources',
    'source_documents', 'source_document_retrievals', 'ingestion_jobs', 'ingestion_job_items', 'alembic_version'}


def protected_fingerprint(db):
    """Stream protected records; directory/jobs/source additions are not catalogue edits."""
    result = {}
    for table in sorted(set(inspect(db.connection()).get_table_names(schema='public')) - MUTABLE_IMPORT_TABLES):
        if table.startswith('unishortlist_'):
            continue
        digest, count = hashlib.sha256(), 0
        for value in db.scalars(text(f'SELECT to_jsonb(t)::text FROM "{table}" t ORDER BY to_jsonb(t)::text')).yield_per(1000):
            digest.update(value.encode())
            digest.update(b'\n')
            count += 1
        result[table] = {'count': count, 'sha256': digest.hexdigest()}
    return result


def _ror(value):
    return str(value or '').rstrip('/').rsplit('/', 1)[-1].casefold()


def reconcile(db, entries):
    """Only report matches. No accepted identifier, review or university is changed."""
    from app.models import CatalogueArchiveRecord, InstitutionIdentifier, University
    keys = {e['ror_id'] for e in entries}
    active, other, names, archives = defaultdict(set), defaultdict(set), defaultdict(set), defaultdict(set)
    def normalized(column):
        return func.regexp_replace(func.rtrim(func.lower(column), '/'), '^https?://(www\\.)?ror\\.org/', '')
    for uid, identifiers in db.execute(select(University.id, University.external_identifiers).where(
            normalized(University.external_identifiers['ror'].astext).in_(keys))):
        active[_ror(identifiers['ror'])].add(str(uid))
    external_values = {str(value).strip().casefold() for e in entries for ident in e['identifiers']
        if isinstance(ident, dict) and ident.get('type') in {'grid', 'isni', 'wikidata'}
        for value in ident.get('all') or []}
    claims = db.execute(select(InstitutionIdentifier.university_id, InstitutionIdentifier.namespace,
        InstitutionIdentifier.identifier_value).where(InstitutionIdentifier.claim_status == 'accepted',
        InstitutionIdentifier.scope != 'campus', or_(
            and_(InstitutionIdentifier.namespace == 'ror', normalized(InstitutionIdentifier.identifier_value).in_(keys)),
            and_(InstitutionIdentifier.namespace.in_(('grid', 'isni', 'wikidata', 'ror_grid', 'ror_isni', 'ror_wikidata')),
                 func.lower(func.btrim(InstitutionIdentifier.identifier_value)).in_(external_values))))).all()
    external = defaultdict(set)
    for uid, namespace, value in claims:
        if namespace == 'ror' and _ror(value) in keys:
            active[_ror(value)].add(str(uid))
        elif namespace in {'grid', 'isni', 'wikidata', 'ror_grid', 'ror_isni', 'ror_wikidata'}:
            external[(namespace.removeprefix('ror_'), value.strip().casefold())].add(str(uid))
    name_values = {e['name'].casefold() for e in entries}
    for uid, country, name in db.execute(select(University.id, University.country_code, University.canonical_name)
            .where(func.lower(University.canonical_name).in_(name_values))):
        names[(country, name.casefold())].add(str(uid))
    if inspect(db.connection()).has_table('catalogue_archive_records'):
        for payload in db.scalars(select(CatalogueArchiveRecord.payload).where(
            CatalogueArchiveRecord.table_name.in_(('universities', 'institution_identifiers')))).yield_per(1000):
            namespace = payload.get('namespace')
            values = (payload.get('external_identifiers') or {}).get('ror') if namespace is None else (
                payload.get('identifier_value') if namespace == 'ror' else None)
            if _ror(values) in keys:
                archives[_ror(values)].add(str(payload.get('university_id') or payload.get('id')))
    result = {}
    for entry in entries:
        key = entry['ror_id']
        for identifier in entry['identifiers']:
            if not isinstance(identifier, dict):
                continue
            for value in identifier.get('all') or []:
                other[key].update(external.get((identifier.get('type'), str(value).strip().casefold()), set()))
        strong = active[key] | other[key]
        hints = names.get((entry['country_code'], entry['name'].casefold()), set())
        status = ('source_conflict' if entry.get('quarantined') else
            'active_identifier_conflict' if len(strong) > 1 else
            'active_identifier_match' if len(active[key]) == 1 else
            'authoritative_match_review' if strong else
            'archived_identity_review' if archives[key] else
            'similar_name_review' if hints else 'reference_only')
        result[key] = {'match_status': status, 'active_university_ids': sorted(strong),
            'similar_name_ids': sorted(hints), 'archived_university_ids': sorted(archives[key]),
            'action': 'No reconciliation or approval performed; use the existing identity review for any future catalogue promotion.'}
    return result


def plan(db, artifact_path, *, batch_size=500, backup_path=None):
    if not 1 <= batch_size <= 2000:
        raise ValueError('Batch size must be between 1 and 2000')
    local, manifest = artifact(artifact_path)
    counts, samples = Counter(), []
    try:
        cursor = local.execute('SELECT payload, quarantined FROM records ORDER BY ordinal')
        while rows := cursor.fetchmany(batch_size):
            entries = [{**json.loads(row[0]), 'quarantined': bool(row[1])} for row in rows]
            for key, match in reconcile(db, entries).items():
                counts[match['match_status']] += 1
                if match['match_status'] != 'reference_only' and len(samples) < 25:
                    samples.append({'ror_id': key, **match})
    finally:
        local.close()
    result = {'operation': 'ror_reference_directory_only', 'target_revision': REVISION,
        'database': dict(db.execute(text('SELECT current_database() AS name, current_user AS role')).mappings().one()),
        'artifact': manifest, 'batch_size': batch_size,
        'protected': protected_fingerprint(db), 'expected_matches': dict(counts), 'match_samples': samples,
        'backup_path': str(Path(backup_path).resolve()) if backup_path else None,
        'backup_sha256': file_hash(backup_path) if backup_path else None,
        'changes': 'Add one directory release, immutable keyed directory rows, source provenance and checkpointed jobs. No university/program/fact/review/archive/user writes.'}
    result['confirmation_sha256'] = hashlib.sha256(stable(result).encode()).hexdigest()
    return result


def verify_plan(db, approved, artifact_path, confirmation, *, resume=False):
    body = {k: v for k, v in approved.items() if k != 'confirmation_sha256'}
    expected = hashlib.sha256(stable(body).encode()).hexdigest()
    if confirmation != expected or approved['confirmation_sha256'] != expected:
        raise ValueError('Exact plan confirmation is required')
    if db.scalar(text('SELECT version_num FROM alembic_version')) != REVISION:
        raise ValueError('Directory migration must be approved/applied first')
    if dict(db.execute(text('SELECT current_database() AS name, current_user AS role')).mappings().one()) != approved['database']:
        raise ValueError('Plan belongs to a different database or role')
    local, manifest = artifact(artifact_path)
    local.close()
    if manifest['artifact_sha256'] != approved['artifact']['artifact_sha256']:
        raise ValueError('Prepared source artifact changed')
    if protected_fingerprint(db) != approved['protected']:
        raise ValueError('Protected catalogue/identity/history changed since plan; inspect and replan')
    if approved.get('backup_path') and file_hash(approved['backup_path']) != approved['backup_sha256']:
        raise ValueError('Pre-import backup no longer matches the plan')
    return manifest


def import_directory(db, artifact_path, approved, confirmation, *, resume_job=None, max_batches=None, fail_after=None):
    from app.models import DirectoryInstitution, DirectoryRelease, IngestionJob, Source, SourceDocument
    manifest = verify_plan(db, approved, artifact_path, confirmation, resume=resume_job is not None)
    release_id = manifest['zip_sha256']
    lock = db.get_bind().connect()
    lock_id = int(release_id[:15], 16)
    if not lock.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': lock_id}):
        lock.close()
        raise ValueError('Another worker is importing this release')
    local = None
    job_id = None
    try:
        release = db.get(DirectoryRelease, release_id)
        if release and release.manifest['artifact_sha256'] != manifest['artifact_sha256']:
            raise ValueError('Release checksum already has a different prepared artifact')
        if release is None:
            source = db.scalar(select(Source).where(Source.metadata_json['adapter_key'].astext == 'ror'))
            if source is None:
                source = Source(name='Research Organization Registry (ROR)', base_url='https://api.ror.org/v2/organizations',
                    source_type='regulator', authority_tier=2, owner_or_publisher='Research Organization Registry',
                    allowed_use_policy='public_dataset', enabled=True,
                    license_notes=manifest['attribution'] + '; CC0-1.0 identity data', metadata_json={'adapter_key': 'ror'})
                db.add(source)
                db.flush()
            if source.allowed_use_policy not in {'public_dataset', 'permitted_fetch', 'licensed_api'}:
                raise ValueError('Source registry does not permit the ROR dataset')
            document = SourceDocument(source_id=source.id, canonical_url=manifest['source_url'],
                title=f"ROR {manifest['release_version']} bulk directory", document_type='zip',
                content_hash=manifest['zip_sha256'], content_excerpt=stable(manifest),
                storage_uri=manifest['zip_path'], http_status=None, fetch_status='fetched', parser_version=WORKER,
                retrieved_at=datetime.fromisoformat(manifest['retrieved_at']),
                last_checked_at=datetime.fromisoformat(manifest['validated_at']),
                last_content_changed_at=datetime.fromisoformat(manifest['retrieved_at']),
                source_published_at=datetime.fromisoformat(manifest['published_at']).date())
            db.add(document)
            db.flush()
            release = DirectoryRelease(id=release_id, source_document_id=document.id, manifest=manifest)
            db.add(release)
            db.flush()
        source = db.get(Source, db.get(SourceDocument, release.source_document_id).source_id)
        if not source.enabled or source.allowed_use_policy not in {'public_dataset', 'permitted_fetch', 'licensed_api'}:
            raise ValueError('Source is disabled or its use policy forbids this import')
        if resume_job:
            job = db.get(IngestionJob, uuid.UUID(str(resume_job)))
            if not job or job.worker_version != WORKER or (job.checkpoint or {}).get('release_id') != release_id:
                raise ValueError('Resume job does not belong to this directory release')
        else:
            job = IngestionJob(source_id=db.get(SourceDocument, release.source_document_id).source_id,
                job_type='discover', status='running', worker_version=WORKER,
                started_at=datetime.now(timezone.utc), checkpoint={'release_id': release_id, 'next_ordinal': 0,
                'artifact_sha256': manifest['artifact_sha256'], 'country_counts': {}, 'match_counts': {},
                'confirmation_sha256': confirmation})
            db.add(job)
            db.flush()
        job_id = job.id
        if job.checkpoint.get('confirmation_sha256') != confirmation:
            raise ValueError('Resume requires the original approved plan')
        job.status, job.error_summary = 'running', None
        db.commit()
        local = sqlite3.connect(f'{Path(artifact_path).resolve().as_uri()}?mode=ro', uri=True)
        batches = 0
        while True:
            job = db.scalar(select(IngestionJob).where(IngestionJob.id == job_id).with_for_update())
            checkpoint = dict(job.checkpoint)
            rows = local.execute('SELECT ordinal, payload, quarantined FROM records WHERE ordinal>? ORDER BY ordinal LIMIT ?',
                                 (checkpoint['next_ordinal'], approved['batch_size'])).fetchall()
            if not rows:
                job.status, job.finished_at = 'succeeded', datetime.now(timezone.utc)
                release = db.get(DirectoryRelease, release_id)
                release.completed_at = release.completed_at or job.finished_at
                db.commit()
                break
            entries = [{**json.loads(row[1]), 'quarantined': bool(row[2])} for row in rows]
            matches = reconcile(db, entries)
            existing = dict(db.execute(select(DirectoryInstitution.ror_id, DirectoryInstitution.record_sha256).where(
                DirectoryInstitution.release_id == release_id, DirectoryInstitution.ror_id.in_([e['ror_id'] for e in entries]))).all())
            if any(e['ror_id'] in existing and existing[e['ror_id']] != e['record_sha256'] for e in entries):
                raise ValueError('Existing release row conflicts with immutable source identity')
            values = [{'release_id': release_id, 'ror_id': e['ror_id'], 'name': e['name'],
                'country_code': e['country_code'], 'search_text': e['search_text'], 'record_sha256': e['record_sha256'],
                'source_ordinal': e['source_ordinal'], 'match_status': matches[e['ror_id']]['match_status'],
                'data': e, 'reconciliation': matches[e['ror_id']]} for e in entries]
            created = list(db.scalars(insert(DirectoryInstitution).values(values).on_conflict_do_nothing().returning(DirectoryInstitution.ror_id)))
            job.records_seen += len(entries)
            job.records_created += len(created)
            job.records_unchanged += len(entries) - len(created)
            country_counts, match_counts = Counter(checkpoint['country_counts']), Counter(checkpoint['match_counts'])
            for e in entries:
                country_counts[e['country_code'] or 'unknown'] += 1
                state = matches[e['ror_id']]['match_status']
                match_counts[state] += 1
                if state not in {'reference_only', 'active_identifier_match'}:
                    job.records_review_required += 1
            checkpoint.update(next_ordinal=rows[-1][0], country_counts=dict(country_counts), match_counts=dict(match_counts))
            job.checkpoint = checkpoint
            db.commit()  # rows and checkpoint succeed or roll back together
            batches += 1
            print(stable({'job_id': str(job_id), 'seen': job.records_seen, 'created': job.records_created,
                'unchanged': job.records_unchanged, 'checkpoint': rows[-1][0]}), flush=True)
            if fail_after and batches == fail_after:
                raise RuntimeError('Injected interruption after committed batch')
            if max_batches and batches >= max_batches:
                job.status = 'partial'
                db.commit()
                break
        return {'job_id': str(job_id), 'status': job.status, 'seen': job.records_seen,
            'created': job.records_created, 'unchanged': job.records_unchanged,
            'review_required': job.records_review_required, 'checkpoint': job.checkpoint}
    except BaseException as exc:
        db.rollback()
        if job_id:
            job = db.get(IngestionJob, job_id)
            job.status, job.error_summary = 'failed', str(exc)[:2000]
            db.commit()
        raise
    finally:
        if local:
            local.close()
        lock.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': lock_id})
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    stage = commands.add_parser('prepare')
    stage.add_argument('--zip', required=True)
    stage.add_argument('--metadata', required=True)
    stage.add_argument('--output', required=True)
    for command in ('plan', 'apply'):
        sub = commands.add_parser(command)
        sub.add_argument('--artifact', required=True)
        sub.add_argument('--target', choices=('test', 'recovery', 'development'), required=True)
        sub.add_argument('--plan', required=True)
        if command == 'plan':
            sub.add_argument('--batch-size', type=int, default=500)
            sub.add_argument('--backup')
        else:
            sub.add_argument('--confirm', required=True)
            sub.add_argument('--resume-job')
            sub.add_argument('--max-batches', type=int)
    args = parser.parse_args()
    if args.command == 'prepare':
        print(stable(prepare(args.zip, json.loads(Path(args.metadata).read_text()), args.output)))
        return
    from app.core.config import settings
    from app.db.safety import verify_development_target, verify_recovery_target, verify_test_target
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    # This explicit operator CLI uses the administrative target, never the API's
    # runtime connection or credentials. Target markers are checked before writes.
    {'test': verify_test_target, 'recovery': verify_recovery_target, 'development': verify_development_target}[args.target](settings.database_url)
    engine = create_engine(settings.database_url)
    with Session(engine) as db:
        if args.command == 'plan':
            db.execute(text('SET TRANSACTION READ ONLY'))
            value = plan(db, args.artifact, batch_size=args.batch_size, backup_path=args.backup)
            Path(args.plan).write_text(json.dumps(value, ensure_ascii=False, indent=2))
            print(stable(value))
        else:
            approved = json.loads(Path(args.plan).read_text())
            if args.target == 'development' and not approved.get('backup_sha256'):
                raise ValueError('Development import requires the exact backed-up plan')
            print(stable(import_directory(db, args.artifact, approved, args.confirm,
                resume_job=args.resume_job, max_batches=args.max_batches)))


if __name__ == '__main__':
    main()
