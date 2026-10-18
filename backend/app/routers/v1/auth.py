"""Authentication endpoints. Tokens are issued as HttpOnly cookies; the browser
never receives raw secrets in response bodies.

NOTE: do not add ``from __future__ import annotations`` here — slowapi wraps these
endpoints in a function whose globals FastAPI uses to resolve annotations, and string
annotations would fail to resolve, dropping the request body parameter.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.core.permissions import get_current_user
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginIn, RegisterIn
from app.services import accounts
from app.services.accounts import role_keys

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_PATH = f"{settings.api_prefix}/auth"


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "roles": role_keys(user),
    }


def _set_auth_cookies(response: Response, user: User) -> None:
    access = create_access_token(str(user.id), role_keys(user))
    refresh = create_refresh_token(str(user.id))
    common = dict(httponly=True, samesite=settings.cookie_samesite, secure=settings.cookie_secure)
    response.set_cookie(ACCESS_COOKIE, access, max_age=settings.jwt_access_ttl_minutes * 60, path="/", **common)
    response.set_cookie(
        REFRESH_COOKIE, refresh, max_age=settings.jwt_refresh_ttl_days * 86400, path=REFRESH_PATH, **common
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/", samesite=settings.cookie_samesite, secure=settings.cookie_secure)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, samesite=settings.cookie_samesite,
                           secure=settings.cookie_secure)


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: settings.rate_limit_auth)
async def register(payload: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = accounts.create_account(
        db, email=payload.email, password=payload.password, display_name=payload.display_name
    )
    _set_auth_cookies(response, user)
    return _user_out(user)


@router.post("/login")
@limiter.limit(lambda: settings.rate_limit_auth)
async def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = accounts.authenticate(db, email=payload.email, password=payload.password)
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    _set_auth_cookies(response, user)
    return _user_out(user)


@router.post("/refresh")
@limiter.limit(lambda: settings.rate_limit_auth)
async def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    payload = decode_token(token, "refresh") if token else None
    if payload is None:
        raise ApiError(401, "INVALID_TOKEN", "Session is invalid or expired.")
    try:
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (KeyError, ValueError):
        user = None
    if user is None or user.deleted_at is not None or user.status.value != "active":
        raise ApiError(401, "INVALID_TOKEN", "Session is invalid or expired.")
    _set_auth_cookies(response, user)
    return _user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    _clear_auth_cookies(response)


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return _user_out(user)
