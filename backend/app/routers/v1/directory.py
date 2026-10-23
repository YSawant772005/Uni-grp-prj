"""Explicitly labelled global references; the existing Discover endpoint is unchanged."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.services import directory

router = APIRouter(tags=['reference directory'])


@router.get('/directory/institutions')
async def institutions(q: str | None = Query(None, max_length=200),
        country: str | None = Query(None, min_length=2, max_length=2),
        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return directory.list_institutions(db, q=q, country=country, page=page, page_size=page_size)


@router.get('/directory/stats')
async def directory_stats(db: Session = Depends(get_db)):
    return directory.stats(db)


@router.get('/admin/directory/reconciliation')
async def reconciliation(status: str | None = Query(None),
        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
        db: Session = Depends(get_db), user=Depends(require_roles('reviewer', 'admin'))):
    return directory.list_institutions(db, status=status, page=page, page_size=page_size, reconciliation=True)
