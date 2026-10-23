"""Memory-bounded official ROR dump validation and local, identity-keyed staging.

This module uses only the standard library and never connects to PostgreSQL.
The SQLite artifact is a resumable input, not an institution approval database.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sqlite3
import unicodedata
import zipfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

CONCEPT = '10.5281/zenodo.6347574'
POLICY = 'active_education_reference_v1'
MAX_RECORD = 2_000_000


def stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def file_hash(path, algorithm='sha256'):
    digest = hashlib.new(algorithm)
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def json_records(handle):
    """Stream a JSON array, refusing malformed/trailing/oversized input."""
    decoder, buffer, eof, first, opened, seen = json.JSONDecoder(), '', False, True, False, False
    def more():
        nonlocal buffer, eof
        chunk = handle.read(65536)
        buffer += chunk
        eof = not chunk
        if len(buffer) > MAX_RECORD:
            raise ValueError('ROR record exceeds bounded parser limit')
    more()
    while True:
        buffer = buffer.lstrip()
        if not buffer and not eof:
            more()
            continue
        if not opened:
            if not buffer.startswith('['):
                raise ValueError('ROR dump must be a JSON array')
            opened, buffer = True, buffer[1:]
            continue
        if buffer.startswith(']'):
            if seen:
                raise ValueError('Trailing comma in ROR array')
            if buffer[1:].strip() or any(chunk.strip() for chunk in iter(lambda: handle.read(65536), '')):
                raise ValueError('Trailing data after ROR array')
            return
        if not first:
            if not buffer.startswith(','):
                raise ValueError('Missing ROR array separator')
            buffer, first = buffer[1:].lstrip(), True
            continue
        try:
            record, end = decoder.raw_decode(buffer)
        except json.JSONDecodeError as exc:
            if eof:
                raise ValueError('Incomplete ROR JSON record') from exc
            more()
            continue
        seen = True
        yield record
        buffer, first = buffer[end:], False
        # A close delimiter follows a completed value, unlike a trailing comma.
        while not buffer.strip() and not eof:
            more()
        buffer = buffer.lstrip()
        if buffer.startswith(']'):
            rest = buffer[1:]
            for chunk in iter(lambda: handle.read(65536), ''):
                if chunk.strip():
                    raise ValueError('Trailing data after ROR array')
            if rest.strip():
                raise ValueError('Trailing data after ROR array')
            return


def normalized_record(raw, ordinal):
    if not isinstance(raw, dict) or not re.fullmatch(r'https://ror\.org/0[a-hj-km-np-tv-z0-9]{6}[0-9]{2}', str(raw.get('id', ''))):
        raise ValueError('invalid_ror_id')
    if raw.get('status') not in {'active', 'inactive', 'withdrawn'}:
        raise ValueError('invalid_status')
    if not isinstance(raw.get('types'), list) or not isinstance(raw.get('names'), list):
        raise ValueError('invalid_v2_shape')
    if raw['status'] != 'active' or 'education' not in raw['types']:
        return None
    names = [n['value'].strip() for n in raw['names'] if isinstance(n, dict)
             and isinstance(n.get('value'), str) and n['value'].strip()]
    name = next((n['value'].strip() for n in raw['names'] if isinstance(n, dict)
                 and 'ror_display' in (n.get('types') or []) and isinstance(n.get('value'), str)), None)
    if not name or not names:
        raise ValueError('missing_display_name')
    countries = list(dict.fromkeys(c for loc in raw.get('locations') or []
        if isinstance(loc, dict) and isinstance(loc.get('geonames_details'), dict)
        and re.fullmatch('[A-Z]{2}', str(c := loc['geonames_details'].get('country_code', '')))))
    def valid_website(value):
        try:
            parts = urlsplit(value)
            return parts.scheme in ('https', 'http') and parts.hostname and not parts.username and not parts.password
        except ValueError:
            return False
    website = next((v for link in raw.get('links') or [] if isinstance(link, dict)
        and link.get('type') == 'website' and isinstance(v := link.get('value'), str)
        and valid_website(v)), None)
    return {'ror_id': raw['id'].rsplit('/', 1)[-1], 'name': name, 'names': names,
            'country_code': countries[0] if countries else None, 'country_codes': countries,
            'website_candidate': website, 'source_types': raw['types'], 'source_status': raw['status'],
            'source_ordinal': ordinal, 'record_sha256': hashlib.sha256(stable(raw).encode()).hexdigest(),
            'identifiers': raw.get('external_ids') or [],
            'search_text': unicodedata.normalize('NFKC', ' '.join(names)).casefold()}


def release_file(metadata):
    if metadata.get('conceptdoi') != CONCEPT or metadata.get('metadata', {}).get('access_right') != 'open':
        raise ValueError('Not an open official ROR concept release')
    info = metadata['metadata']
    if date.fromisoformat(info['publication_date']) > datetime.now(timezone.utc).date():
        raise ValueError('Release publication date is in the future')
    license_id = (info.get('license') or {}).get('id', '').casefold()
    if license_id not in {'cc0-1.0', 'cc-zero'} or 'Research Organization Registry' not in stable(info.get('creators')):
        raise ValueError('Official ROR CC0 publisher/licence is not established')
    files = [f for f in metadata.get('files') or [] if re.fullmatch(r'v2\.\d+(?:\.\d+)?-\d{4}-\d{2}-\d{2}-ror-data\.zip', f.get('key', ''))]
    if len(files) != 1 or not 0 < files[0].get('size', 0) <= 250_000_000:
        raise ValueError('Expected one bounded ROR v2 ZIP')
    item = files[0]
    parts = urlsplit(item['links']['self'])
    if parts.scheme != 'https' or parts.hostname != 'zenodo.org' or parts.username or parts.password:
        raise ValueError('ROR download is not the official HTTPS Zenodo file')
    return item


def prepare(zip_path, metadata, output):
    zip_path, output = Path(zip_path), Path(output)
    item = release_file(metadata)
    if zip_path.stat().st_size != item['size'] or 'md5:' + file_hash(zip_path, 'md5') != item['checksum']:
        raise ValueError('Official ZIP size/checksum mismatch')
    source_sha = file_hash(zip_path)
    temporary = output.with_suffix(output.suffix + '.part')
    if output.exists() or temporary.exists():
        raise ValueError('Choose a new artifact path; existing staging artifacts are never overwritten')
    output.parent.mkdir(parents=True, exist_ok=True)
    stats = Counter({key: 0 for key in ('source_records', 'eligible_records', 'excluded_non_active_education',
        'invalid_records', 'duplicate_identifiers', 'conflicting_identifiers', 'missing_websites')})
    countries, samples = Counter(), []
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript('''
            CREATE TABLE records (ror_id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE,
                country_code TEXT, record_sha256 TEXT NOT NULL, payload TEXT NOT NULL,
                quarantined INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX records_order ON records(ordinal);
            CREATE TABLE issues (ordinal INTEGER, ror_id TEXT, reason TEXT, payload TEXT);
            CREATE TABLE manifest (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
        ''')
        with zipfile.ZipFile(zip_path) as archive:
            members = [i for i in archive.infolist() if i.filename.endswith('.json')]
            if len(members) != 1 or members[0].file_size > 1_000_000_000:
                raise ValueError('Expected one bounded v2 JSON member')
            member = members[0]
            with io.TextIOWrapper(archive.open(member), encoding='utf-8') as stream:
                for ordinal, raw in enumerate(json_records(stream), 1):
                    stats['source_records'] += 1
                    try:
                        entry = normalized_record(raw, ordinal)
                    except (ValueError, TypeError, KeyError) as exc:
                        stats['invalid_records'] += 1
                        reason = str(exc)[:200]
                        connection.execute('INSERT INTO issues VALUES (?, ?, ?, ?)',
                            (ordinal, raw.get('id') if isinstance(raw, dict) else None, reason, stable(raw)))
                        if len(samples) < 20:
                            samples.append({'ordinal': ordinal, 'reason': reason})
                        continue
                    if entry is None:
                        stats['excluded_non_active_education'] += 1
                        continue
                    previous = connection.execute('SELECT record_sha256 FROM records WHERE ror_id=?', (entry['ror_id'],)).fetchone()
                    if previous:
                        stats['duplicate_identifiers'] += 1
                        if previous[0] != entry['record_sha256']:
                            stats['conflicting_identifiers'] += 1
                            connection.execute('UPDATE records SET quarantined=1 WHERE ror_id=?', (entry['ror_id'],))
                            connection.execute('INSERT INTO issues VALUES (?, ?, ?, ?)',
                                (ordinal, entry['ror_id'], 'conflicting_duplicate_ror', stable(raw)))
                        continue
                    connection.execute('INSERT INTO records VALUES (?, ?, ?, ?, ?, 0)',
                        (entry['ror_id'], ordinal, entry['country_code'], entry['record_sha256'], stable(entry)))
                    countries[entry['country_code'] or 'unknown'] += 1
                    stats['eligible_records'] += 1
                    if not entry['website_candidate']:
                        stats['missing_websites'] += 1
                    if ordinal % 1000 == 0:
                        connection.commit()
        manifest = {'format': 'unishortlist-ror-directory-v1', 'policy': POLICY,
            'release_doi': metadata['doi'], 'concept_doi': CONCEPT, 'record_id': str(metadata['id']),
            'release_version': item['key'].split('-202')[0], 'published_at': metadata['metadata']['publication_date'],
            'retrieved_at': datetime.fromtimestamp(zip_path.stat().st_mtime, timezone.utc).isoformat(),
            'retrieval_time_basis': 'validated_local_download_mtime',
            'validated_at': datetime.now(timezone.utc).isoformat(), 'source_url': item['links']['self'],
            'filename': item['key'], 'zip_size': item['size'], 'zip_sha256': source_sha,
            'zip_path': str(zip_path.resolve()), 'metadata_sha256': hashlib.sha256(stable(metadata).encode()).hexdigest(),
            'published_checksum': item['checksum'], 'json_member': member.filename,
            'licence': 'CC0-1.0', 'attribution': 'Research Organization Registry (ROR); location data: GeoNames, CC BY 4.0',
            'stats': dict(stats), 'countries': dict(sorted(countries.items())), 'invalid_samples': samples,
            'limitation': 'Active ROR education-type references; not accreditation or verified Master\'s availability. Country is the first reported ROR location.'}
        connection.execute('INSERT INTO manifest VALUES (1, ?)', (stable(manifest),))
        connection.commit()
    except BaseException:
        connection.close()
        temporary.unlink(missing_ok=True)
        raise
    connection.close()
    temporary.replace(output)
    return {**manifest, 'artifact_sha256': file_hash(output), 'artifact_path': str(output.resolve())}


def artifact(path):
    path = Path(path).resolve()
    db = sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)
    manifest = json.loads(db.execute('SELECT payload FROM manifest WHERE id=1').fetchone()[0])
    if manifest.get('format') != 'unishortlist-ror-directory-v1' or manifest.get('policy') != POLICY:
        db.close()
        raise ValueError('Unsupported directory artifact format or filter')
    return db, {**manifest, 'artifact_sha256': file_hash(path), 'artifact_path': str(path)}
