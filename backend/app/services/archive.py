"""Read-only historical catalogue context for authorized reviewers."""
from __future__ import annotations

from sqlalchemy import inspect, select

from app.core.errors import ApiError
from app.models import CatalogueArchiveRecord, CatalogueResetOperation, InstitutionIdentityReview


def available(db) -> bool:
    return inspect(db.get_bind()).has_table("catalogue_reset_operations", schema="public")


def active_identity_clause(db):
    # Read compatibility while the additive archive migration awaits approval.
    return InstitutionIdentityReview.archived_operation_id.is_(None) if available(db) else True


def record_context(db, table_name, record_id):
    if not available(db):
        return None
    row = db.scalar(select(CatalogueArchiveRecord).where(
        CatalogueArchiveRecord.table_name == table_name,
        CatalogueArchiveRecord.record_key == str(record_id))
        .join(CatalogueResetOperation, CatalogueResetOperation.id == CatalogueArchiveRecord.operation_id)
        .order_by(CatalogueResetOperation.created_at, CatalogueResetOperation.id).limit(1))
    return {"operation_id": row.operation_id, "original_record": row.payload} if row else None


def operations(db):
    if not available(db):
        return {"items": [], "archive_available": False}
    rows = db.scalars(select(CatalogueResetOperation).order_by(CatalogueResetOperation.created_at.desc())).all()
    return {"archive_available": True, "items": [{"id": row.id, "created_at": row.created_at,
             "operator": row.operator, "reason": row.reason, "revision": row.original_revision,
             "backup_sha256": row.backup_sha256, "manifest": row.manifest} for row in rows]}


def records(db, operation_id, *, table_name=None, page=1, page_size=20):
    if not available(db) or db.get(CatalogueResetOperation, operation_id) is None:
        raise ApiError(404, "NOT_FOUND", "Catalogue archive not found.")
    from sqlalchemy import func
    conds = [CatalogueArchiveRecord.operation_id == operation_id]
    if table_name:
        conds.append(CatalogueArchiveRecord.table_name == table_name)
    total = db.scalar(select(func.count()).select_from(CatalogueArchiveRecord).where(*conds)) or 0
    rows = db.scalars(select(CatalogueArchiveRecord).where(*conds).order_by(
        CatalogueArchiveRecord.table_name, CatalogueArchiveRecord.record_key)
        .offset((page-1)*page_size).limit(page_size)).all()
    return {"items": [{"table_name": row.table_name, "record_key": row.record_key,
                       "payload": row.payload, "row_sha256": row.row_sha256} for row in rows],
            "page": page, "page_size": page_size, "total_items": total,
            "total_pages": (total+page_size-1)//page_size}
