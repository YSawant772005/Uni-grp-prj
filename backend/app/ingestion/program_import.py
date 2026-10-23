"""Freeze official programme responses, plan exact candidate additions, reuse the pipeline.

This operator-only tool never makes review decisions. Development apply requires
an exact backed-up plan. The complete operation commits atomically; retries are
idempotent and never overwrite an existing programme.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.ingestion.adapters.base import RunContext, SourceAdapter
from app.ingestion.http import Fetcher, HttpResult
from app.ingestion.registry import FETCHABLE_POLICIES, get_adapter, get_spec
from app.ingestion.ror_dump import file_hash, stable
from app.ingestion.validate import validate_institution, validate_program

SOURCES = {'duo_rio_masters', 'fr_monmaster'}
VERSION = 'program-import-1'


def digest(value):
    return hashlib.sha256(stable(value).encode()).hexdigest()


def code_hash():
    root = Path(__file__).parent
    return digest({str(p.relative_to(root)): file_hash(p) for p in [
        root/'program_import.py', root/'pipeline.py', root/'persist.py', root/'validate.py',
        root/'adapters/duo_rio.py', root/'adapters/monmaster.py']})


def capture(source_key, output, metadata_path, *, limit, pages):
    if source_key not in SOURCES:
        raise ValueError('Only the two validated government programme connectors are supported')
    spec = get_spec(source_key)
    if not spec.enabled or spec.allowed_use_policy not in FETCHABLE_POLICIES:
        raise ValueError('Source permission is not enabled')
    metadata = json.loads(Path(metadata_path).read_text())
    if source_key == 'duo_rio_masters':
        info = metadata.get('result') or {}
        if not metadata.get('success') or info.get('name') != 'ho_opleidingsoverzicht' or info.get('license_id') != 'cc-by':
            raise ValueError('Official DUO metadata/licence is not established')
        version = next(r['last_modified'] for r in info['resources'] if r['id'] == 'ffffa7ad-e6a2-4ba7-9fc2-a09df4128555')
    else:
        info = (metadata.get('metas') or {}).get('default') or {}
        if metadata.get('dataset_id') != 'fr-esr-mon_master' or 'Licence Ouverte' not in info.get('license', ''):
            raise ValueError('Official Mon Master metadata/licence is not established')
        version = info['modified']
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a new snapshot directory; source snapshots are never overwritten')
    output.mkdir(parents=True)
    old_cache = os.environ.get('INGESTION_CACHE_DIR')
    os.environ['INGESTION_CACHE_DIR'] = str(output/'.adapter-cache')
    requests = []
    class Recorder:
        def get(self, url, **kwargs):
            if not url.startswith(spec.base_url+'?'):
                raise ValueError('Unexpected source URL')
            result = fetcher.get(url, **kwargs)
            if result.status != 200 or len(result.content) > 10_000_000:
                raise ValueError('Expected a bounded fresh HTTP 200 official dataset response')
            filename = digest(url)+'.json'
            (output/filename).write_bytes(result.content)
            requests.append({'url': url, 'filename': filename, 'sha256': file_hash(output/filename),
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'status': result.status,
                'headers': {k:v for k,v in result.headers.items() if k.lower() in ('etag','last-modified','content-type')},
                'attempts': result.attempts})
            return result
    try:
        with Fetcher(user_agent='UniShortlist/1.0 (bounded official programme snapshot)',
                timeout=spec.timeout_seconds, rps=spec.request_rps, max_workers=1) as fetcher:
            batches = list(get_adapter(source_key).iter_batches(RunContext(fetcher=Recorder(),
                checkpoint={'bounded_bulk_snapshot':True}, max_records=limit, max_pages=pages)))
        manifest = {'format': VERSION, 'source_key': source_key, 'source_version': version,
            'source_metadata': metadata, 'source_spec': asdict(spec), 'limit': limit, 'max_pages': pages,
            'requests': requests, 'captured_at': datetime.now(timezone.utc).isoformat(),
            'programme_candidates': sum(len(i.programs) for b in batches for i in b.institutions),
            'warnings': dict(Counter(w for b in batches for w in b.warnings)),
            'attribution': f'{spec.owner_or_publisher}; UniShortlist selected/normalized identity and programme fields; no admission availability inferred.'}
        (output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        return {'snapshot': str(output/'manifest.json'), 'sha256': file_hash(output/'manifest.json'),
                'programmes': manifest['programme_candidates'], 'requests': len(requests), 'warnings': manifest['warnings']}
    finally:
        if old_cache is None:
            os.environ.pop('INGESTION_CACHE_DIR', None)
        else:
            os.environ['INGESTION_CACHE_DIR'] = old_cache


def load(path):
    path = Path(path).resolve()
    manifest = json.loads(path.read_text())
    if manifest.get('format') != VERSION or manifest.get('source_key') not in SOURCES:
        raise ValueError('Unsupported programme snapshot')
    for request in manifest['requests']:
        file = path.parent/request['filename']
        if file.parent != path.parent or file_hash(file) != request['sha256']:
            raise ValueError('Captured source response checksum changed')
    return path, manifest


def batches(path):
    path, manifest = load(path)
    requests = {r['url']: r for r in manifest['requests']}
    class FrozenFetcher:
        def get(self, url, **kwargs):
            if url not in requests:
                raise ValueError('Frozen source snapshot does not contain the requested URL; no network fallback')
            record = requests[url]
            return HttpResult(url=url, status=record['status'], content=(path.parent/record['filename']).read_bytes(),
                              headers=record['headers'], attempts=0)
    # The adapter's ordinary online parser is reused with a network-free fetcher.
    # Restore the actual acquisition time; replay is not a new source retrieval.
    from app.ingestion.adapters.duo_rio import DuoRioAdapter
    from app.ingestion.adapters.monmaster import MonMasterAdapter
    adapter = {'duo_rio_masters':DuoRioAdapter, 'fr_monmaster':MonMasterAdapter}[manifest['source_key']]()
    for batch in adapter.iter_batches(RunContext(fetcher=FrozenFetcher(), checkpoint={'frozen_replay':True,'bounded_bulk_snapshot':True},
            max_records=manifest['limit'], max_pages=manifest['max_pages'])):
        request = requests[batch.document.canonical]
        batch.document.retrieved_at = datetime.fromisoformat(request['retrieved_at'])
        batch.document.retrieval_attempt_count = 0
        batch.document.source_date = datetime.fromisoformat(manifest['source_version']).date()
        yield batch


def existing_state(db, reference=None):
    """Fingerprint original rows, while allowing only append operations afterwards."""
    state = {}
    schema = inspect(db.connection())
    tables = sorted(set(schema.get_table_names(schema='public')) - {'sources'})
    for table in tables:
        columns = schema.get_pk_constraint(table)['constrained_columns']
        previous = reference.get(table) if reference else None
        # Large independent directory/archive snapshots must remain wholly unchanged.
        whole = table.startswith(('directory_', 'catalogue_')) or table == 'alembic_version'
        keys = set(previous['keys']) if previous and previous['keys'] is not None else None
        row_hash, selected = hashlib.sha256(), []
        for row in db.scalars(text(f'SELECT to_jsonb(t) FROM "{table}" t ORDER BY to_jsonb(t)::text')).yield_per(1000):
            key = stable([row.get(c) for c in columns])
            if previous and keys is not None and key not in keys:
                continue
            row_hash.update(stable(row).encode()); row_hash.update(b'\n')
            if not whole:
                selected.append(key)
        state[table] = {'keys': None if whole else sorted(selected), 'sha256': row_hash.hexdigest()}
    return state


def selection(db, snapshot):
    from app.ingestion.persist import InstitutionResolver
    from app.models import CatalogueArchiveRecord, ProgramIdentifier, Source
    _, manifest = load(snapshot)
    source_key = manifest['source_key']
    # Adapters deduplicate repeated rows. Inspect the original rows first so a
    # repeated UUID/IFC with a different owner or title cannot become first-wins.
    identities, raw_counts = defaultdict(set), Counter()
    board_rows = []
    path = Path(snapshot).resolve()
    for request in manifest['requests']:
        payload = json.loads((path.parent/request['filename']).read_bytes())
        for row in (payload['result']['records'] if source_key=='duo_rio_masters' else payload['results']):
            if source_key=='duo_rio_masters':
                from app.ingestion.adapters.duo_rio import _stable_offering_id
                identifier = _stable_offering_id(row)
                owner, title = row.get('ONDERWIJSAANBIEDERID'), row.get('NAAM_LANG') or row.get('INTERNATIONALE_NAAM')
                key = 'duo:offering:'+identifier if identifier else None
            else:
                from app.ingestion.adapters.monmaster import _program_title
                owner = row.get('eta_uai')
                title = _program_title(str(row.get('mention') or ''),row.get('parcours'))
                key = 'fr-monmaster:ifc:'+str(row['ifc']) if row.get('ifc') else None
            if key and owner and title:
                identities[key].add((str(owner).strip().casefold(),' '.join(str(title).split()).casefold()))
                raw_counts[key] += 1
                if (source_key=='duo_rio_masters' and row.get('ONDERWIJSBESTUURID')
                        and not str(row.get('SAMENWERKEND_MET') or '').strip()
                        and not str(row.get('BUITENLANDSEPARTNER') or '').strip()
                        and 'joint degree' not in str(title).casefold()):
                    board_rows.append((key,str(row['ONDERWIJSBESTUURID']),str(owner)))
    source_conflicts = {key for key, values in identities.items() if len(values)>1}
    source = db.scalar(select(Source).where(Source.metadata_json['adapter_key'].astext == source_key))
    spec = get_spec(source_key)
    if (not spec.enabled or spec.allowed_use_policy not in FETCHABLE_POLICIES
            or source is not None and (not source.enabled or source.allowed_use_policy not in FETCHABLE_POLICIES)):
        raise ValueError('Programme source is disabled or its registry/database policy forbids import')
    resolver = InstitutionResolver(db)
    existing = set(db.scalars(select(ProgramIdentifier.external_key).where(ProgramIdentifier.source_key == source_key)))
    historical_ids, historical_names = set(), set()
    for payload in db.scalars(select(CatalogueArchiveRecord.payload).where(
            CatalogueArchiveRecord.table_name.in_(('universities','institution_identifiers')))).yield_per(1000):
        if payload.get('canonical_name'):
            historical_names.add((payload.get('country_code'), payload['canonical_name'].casefold().strip()))
        for namespace,value in (payload.get('external_identifiers') or {}).items():
            historical_ids.add((namespace,str(value).strip().casefold()))
        if payload.get('namespace'):
            historical_ids.add((payload['namespace'],str(payload.get('identifier_value')).strip().casefold()))
    institutions, programmes, held, duplicate = {}, {}, {}, 0
    invalid = []
    for batch in batches(snapshot):
        for candidate in batch.institutions:
            key = candidate.external_key
            if validate_institution(candidate):
                invalid.append(key);continue
            target, match = resolver.resolve(candidate, source.id if source else None)
            archive_match = (candidate.country_code,candidate.name.casefold().strip()) in historical_names or any(
                (namespace,str(value).strip().casefold()) in historical_ids for namespace,value in candidate.identifiers.items())
            if match not in (None,'external_id','reviewed_link') or (archive_match and not target):
                held[key] = {'name':candidate.name, 'reason':match or 'archived_identity_requires_reconciliation'}
                continue
            value = {'name': candidate.name, 'country_code':candidate.country_code,
                     'identifiers':candidate.identifiers, 'existing_university_id':str(target) if target else None}
            if key in institutions and institutions[key] != value:
                raise ValueError('One source provider identifier has conflicting institution identities')
            institutions[key] = value
            for program in candidate.programs:
                if program.external_key in source_conflicts:
                    continue
                if validate_program(program):
                    invalid.append(program.external_key);continue
                identity = {'institution_key':key,'title':program.title,'degree_level':program.degree_level}
                previous = programmes.get(program.external_key)
                if previous and previous != identity:
                    raise ValueError('One source programme identifier has conflicting ownership or title')
                duplicate += previous is not None
                programmes[program.external_key] = identity
    if source_key=='duo_rio_masters':
        boards = defaultdict(set)
        for key,board,owner in board_rows:
            if key in programmes:
                boards[board].add(owner)
        grouped_providers = {owner:board for board,owners in boards.items() if len(owners)>1 for owner in owners}
        for key,institution in institutions.items():
            provider_id = institution['identifiers']['rio_provider_id']
            if provider_id in grouped_providers or re.search(r'\b(faculteit|faculty|department|masterprogramma)\b',institution['name'],re.I):
                held[key] = {'name':institution['name'], 'reason':'provider_subunit_or_shared_board_requires_identity_review',
                             'board_id':grouped_providers.get(provider_id)}
    additions = {k:v for k,v in programmes.items() if k not in existing and v['institution_key'] not in held}
    needed = {p['institution_key'] for p in additions.values()}
    return {'institutions':{k:v for k,v in institutions.items() if k in needed},
            'programmes':additions,'held_institutions':held,'invalid_keys':invalid,
            'existing_programmes_skipped':len(set(programmes)&existing),'duplicate_candidates':duplicate,
            'source_duplicate_rows':sum(n-1 for n in raw_counts.values()),
            'source_identity_conflicts':sorted(source_conflicts)}


def plan(db, snapshots, backup):
    selections = []
    for snapshot in snapshots:
        path, manifest = load(snapshot)
        selections.append({'snapshot':str(path),'snapshot_sha256':file_hash(path),'source_key':manifest['source_key'],
                           'source_version':manifest['source_version'], **selection(db,path)})
    if len({s['source_key'] for s in selections}) != len(selections):
        raise ValueError('Each source may appear only once in an operation')
    result = {'format':VERSION, 'database':dict(db.execute(text('SELECT current_database() AS name,current_user AS role')).mappings().one()),
        'revision':db.scalar(text('SELECT version_num FROM alembic_version')), 'code_sha256':code_hash(),
        'sources':selections,'original_rows':existing_state(db),'backup_path':str(Path(backup).resolve()),
        'backup_sha256':file_hash(backup),'expected_programmes':sum(len(s['programmes']) for s in selections),
        'expected_new_institutions':sum(not i['existing_university_id'] for s in selections for i in s['institutions'].values()),
        'publication':'All additions are unpublished candidates; no reviewer decisions or existing programme writes.'}
    return {**result,'confirmation_sha256':digest(result)}


class SelectedAdapter(SourceAdapter):
    def __init__(self, snapshot, selected):
        self.snapshot, self.selected = snapshot, set(selected)
    def iter_batches(self, ctx):
        seen = set()
        for batch in batches(self.snapshot):
            candidates = []
            for institution in batch.institutions:
                institution.programs = [p for p in institution.programs if p.external_key in self.selected and p.external_key not in seen]
                seen.update(p.external_key for p in institution.programs)
                if institution.programs:
                    candidates.append(institution)
            batch.institutions = candidates
            used = {p.discipline_key for i in candidates for p in i.programs}
            batch.fields = [f for f in batch.fields if f.key in used]
            if candidates:
                yield batch


def apply(engine, approved, confirmation):
    from app.ingestion.pipeline import RunOptions, run_source
    from app.ingestion.registry import _ADAPTERS
    from app.models import Program,ProgramIdentifier,University
    if approved.get('confirmation_sha256') != confirmation or digest({k:v for k,v in approved.items() if k!='confirmation_sha256'}) != confirmation:
        raise ValueError('Exact programme import confirmation is required')
    if code_hash() != approved['code_sha256'] or file_hash(approved['backup_path']) != approved['backup_sha256']:
        raise ValueError('Importer code or pre-import backup changed')
    summaries = []
    # Existing pipeline commits release savepoints; this outer transaction makes
    # every planned source addition atomic, including verification failures.
    with engine.begin() as connection, Session(bind=connection,join_transaction_mode='create_savepoint',
                                               autoflush=False,expire_on_commit=False) as db:
        db.execute(text('SELECT pg_advisory_xact_lock(810932712)'))
        identity = dict(db.execute(text('SELECT current_database() AS name,current_user AS role')).mappings().one())
        if identity != approved['database'] or db.scalar(text('SELECT version_num FROM alembic_version')) != approved['revision']:
            raise ValueError('Plan belongs to another database, role or schema')
        if existing_state(db,approved['original_rows']) != approved['original_rows']:
            raise ValueError('Existing protected records changed; inspect and approve a fresh plan')
        for entry in approved['sources']:
            if file_hash(entry['snapshot']) != entry['snapshot_sha256']:
                raise ValueError('Programme snapshot manifest changed')
            load(entry['snapshot'])
            current = selection(db,entry['snapshot'])
            expected = set(entry['programmes'])
            # Repeating a completed exact operation creates no programme writes.
            if set(current['programmes']) - expected or current['held_institutions'] != entry['held_institutions']:
                raise ValueError('Source identity selection changed since planning')
            old = _ADAPTERS[entry['source_key']]
            _ADAPTERS[entry['source_key']] = SelectedAdapter(entry['snapshot'],set(current['programmes']) & expected)
            try:
                result = run_source(entry['source_key'], RunOptions(max_records=load(entry['snapshot'])[1]['limit'],offline=True),db=db)
            finally:
                _ADAPTERS[entry['source_key']] = old
            known_warnings = Counter(load(entry['snapshot'])[1]['warnings'])
            if (result.status not in ('succeeded','partial')
                    or result.counters.programs_created != len(set(current['programmes']) & expected)
                    or result.counters.validation_errors or result.counters.http_failures
                    or result.counters.review or result.counters.rejected
                    or not Counter(result.counters.warnings) <= known_warnings):
                raise ValueError(f'Import did not meet the exact plan: {result.as_dict()}')
            summaries.append(result.as_dict())
        if existing_state(db,approved['original_rows']) != approved['original_rows']:
            raise ValueError('Import changed an original programme, review, evidence, archive or user row; rolling back')
        for entry in approved['sources']:
            rows = db.execute(select(ProgramIdentifier.external_key,Program.publication_status,University.external_identifiers,Program.canonical_name,Program.degree_level)
                .join(Program,Program.id==ProgramIdentifier.program_id).join(University,University.id==Program.university_id)
                .where(ProgramIdentifier.source_key==entry['source_key'],ProgramIdentifier.external_key.in_(entry['programmes']))).all()
            if len(rows) != len(entry['programmes']):
                raise ValueError('Planned programmes are missing')
            for key,status,identifiers,title,level in rows:
                identity = entry['programmes'][key]
                provider = entry['institutions'][identity['institution_key']]
                if status != 'candidate' or title != identity['title'] or level != 'masters' or any(
                        identifiers.get(k) != v for k,v in provider['identifiers'].items()):
                    raise ValueError('Planned programme identity, owner or candidate status is inconsistent')
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    capture_parser = sub.add_parser('capture')
    capture_parser.add_argument('--source',choices=sorted(SOURCES),required=True)
    capture_parser.add_argument('--output',required=True)
    capture_parser.add_argument('--metadata',required=True)
    capture_parser.add_argument('--limit',type=int,required=True)
    capture_parser.add_argument('--max-pages',type=int,default=100)
    for command in ('plan','apply'):
        p = sub.add_parser(command)
        p.add_argument('--target',choices=('test','recovery','development'),required=True)
        p.add_argument('--plan',required=True)
        if command=='plan':
            p.add_argument('--snapshot',action='append',required=True)
            p.add_argument('--backup',required=True)
        else:p.add_argument('--confirm',required=True)
    args = parser.parse_args()
    if args.command=='capture':
        print(stable(capture(args.source,args.output,args.metadata,limit=args.limit,pages=args.max_pages)));return
    from sqlalchemy import create_engine
    from app.core.config import settings
    from app.db.safety import verify_development_target,verify_test_target,verify_recovery_target
    {'test':verify_test_target,'recovery':verify_recovery_target,'development':verify_development_target}[args.target](settings.database_url)
    engine = create_engine(settings.database_url)
    if args.command=='plan':
        with Session(engine) as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            value = plan(db,args.snapshot,args.backup)
        Path(args.plan).write_text(json.dumps(value,ensure_ascii=False,indent=2))
        print(stable({k:v for k,v in value.items() if k not in ('sources','original_rows')}))
    else:
        print(stable(apply(engine,json.loads(Path(args.plan).read_text()),args.confirm)))


if __name__=='__main__':
    main()
