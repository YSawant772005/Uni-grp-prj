"""Health and metadata endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
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
        db.execute(text("SELECT 1"))
    except Exception:
        return {"status": "unavailable", "database": "unreachable"}
    return {"status": "ready", "database": "ok"}


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
