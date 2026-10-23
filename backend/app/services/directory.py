"""Reference directory reads never relax the separate Master's publication gate."""
import unicodedata

from sqlalchemy import func, inspect, select

from app.core.errors import ApiError
from app.models import DirectoryInstitution, DirectoryRelease

STATES = {'reference_only', 'active_identifier_match', 'active_identifier_conflict',
          'authoritative_match_review', 'archived_identity_review', 'similar_name_review', 'source_conflict'}
PUBLIC_PROVENANCE = ('release_doi', 'release_version', 'published_at', 'retrieved_at',
                     'zip_sha256', 'published_checksum', 'licence', 'attribution', 'limitation')


def list_institutions(db, *, q=None, country=None, page=1, page_size=20, reconciliation=False, status=None):
    if not inspect(db.connection()).has_table('directory_releases'):
        raise ApiError(503, 'DIRECTORY_NOT_DEPLOYED', 'The reference directory migration has not been deployed.')
    if status and status not in STATES:
        raise ApiError(422, 'VALIDATION_ERROR', 'Unknown directory reconciliation status.')
    release = db.scalar(select(DirectoryRelease).where(DirectoryRelease.completed_at.is_not(None))
        .order_by(DirectoryRelease.manifest['published_at'].astext.desc(), DirectoryRelease.created_at.desc()).limit(1))
    empty = {'items': [], 'page': page, 'page_size': page_size, 'total_items': 0,
             'total_pages': 0, 'directory_status': 'not_loaded', 'release': None}
    if release is None:
        return empty
    conditions = [DirectoryInstitution.release_id == release.id]
    if not reconciliation:
        conditions.append(DirectoryInstitution.match_status != 'source_conflict')
    elif status:
        conditions.append(DirectoryInstitution.match_status == status)
    else:
        conditions.append(DirectoryInstitution.match_status.notin_(('reference_only', 'active_identifier_match')))
    if country:
        conditions.append(DirectoryInstitution.country_code == country.upper())
    if q:
        query = unicodedata.normalize('NFKC', q).casefold().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        conditions.append(DirectoryInstitution.search_text.like('%' + query + '%', escape='\\'))
    total = db.scalar(select(func.count()).select_from(DirectoryInstitution).where(*conditions)) or 0
    rows = db.scalars(select(DirectoryInstitution).where(*conditions)
        .order_by(DirectoryInstitution.name, DirectoryInstitution.ror_id)
        .offset((page-1)*page_size).limit(page_size)).all()
    manifest = release.manifest
    items = []
    for row in rows:
        data = row.data
        item = {'ror_id': row.ror_id, 'name': row.name, 'names': data['names'],
            'country_code': row.country_code, 'country_codes': data['country_codes'],
            'record_status': 'unreviewed_reference', 'source_status': data['source_status'],
            'source_types': data['source_types'], 'masters_availability': 'not_assessed',
            'website': {'url': data['website_candidate'], 'status': 'candidate' if data['website_candidate'] else 'unavailable'},
            'source_record_url': f'https://ror.org/{row.ror_id}', 'source_ordinal': row.source_ordinal,
            'source_record_sha256': row.record_sha256}
        if reconciliation:
            item.update(match_status=row.match_status, reconciliation=row.reconciliation)
        items.append(item)
    return {'items': items, 'page': page, 'page_size': page_size, 'total_items': total,
        'total_pages': (total+page_size-1)//page_size, 'directory_status': 'reference_only',
        'release': {k: manifest[k] for k in PUBLIC_PROVENANCE},
        'notice': 'ROR education references are not institution approvals, accreditation claims, or published Master\'s offerings.'}


def stats(db):
    if not inspect(db.connection()).has_table('directory_releases'):
        return {'directory_status': 'not_deployed', 'records': 0, 'countries': []}
    release = db.scalar(select(DirectoryRelease).where(DirectoryRelease.completed_at.is_not(None))
        .order_by(DirectoryRelease.manifest['published_at'].astext.desc(), DirectoryRelease.created_at.desc()).limit(1))
    if not release:
        return {'directory_status': 'not_loaded', 'records': 0, 'countries': []}
    countries = db.execute(select(DirectoryInstitution.country_code, func.count()).where(
        DirectoryInstitution.release_id == release.id, DirectoryInstitution.match_status != 'source_conflict')
        .group_by(DirectoryInstitution.country_code).order_by(DirectoryInstitution.country_code)).all()
    return {'directory_status': 'reference_only', 'records': sum(n for _, n in countries),
        'countries_count': sum(c is not None for c, _ in countries),
        'countries': [{'country_code': c, 'records': n} for c, n in countries],
        'source': {k: release.manifest[k] for k in PUBLIC_PROVENANCE}}
