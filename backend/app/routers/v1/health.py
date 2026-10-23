"""Health and metadata endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(db: Session = Depends(get_db)):
    try:
        schema_exists = db.execute(
            text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        ).scalar_one()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "unreachable", "schema": "missing_or_unavailable"})
    if not schema_exists:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "ok", "schema": "not_initialized"})
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "ok", "schema": "not_initialized"})
    if revision is None:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "ok", "schema": "not_initialized"})
    from app.models import Base
    columns = {}
    for table_name, column_name in db.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='public'")):
        columns.setdefault(table_name, set()).add(column_name)
    optional_tables = {"catalogue_archive_records", "catalogue_reset_operations", "source_document_retrievals"}
    optional_columns = {"source_documents": {"source_published_at", "academic_period", "last_checked_at", "last_content_changed_at"},
                        "institution_reviews": {"archived_operation_id"},
                        "institution_identity_reviews": {"archived_operation_id"}}
    if any(set(table.columns.keys()) - optional_columns.get(table.name, set()) - columns.get(table.name, set())
           for table in Base.metadata.tables.values() if table.name not in optional_tables):
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "ok", "schema": "incompatible"})
    result = {"status": "ready", "database": "ok", "schema": "initialized"}
    if settings.unishortlist_test_mode:
        result["database_target"] = "isolated_test"
    return result


@router.get("/meta")
async def meta():
    return {
        "name": "University Shortlisting Tool API",
        "version": "1.0.0",
        "environment": settings.environment,
        "base_path": settings.api_prefix,
        "features": {
            "catalogue": True,
            "recommendations": True,
            "finance": True,
            "admin_review": True,
        },
    }
