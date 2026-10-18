"""Authentication/authorization dependencies. Ownership and roles are enforced
server-side only; client-supplied identity fields are never trusted."""
from __future__ import annotations

import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import decode_token
from app.db.session import get_db
from app.models import User, UserStatus


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get("access_token")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise ApiError(401, "UNAUTHENTICATED", "Authentication required.")
    payload = decode_token(token, "access")
    if payload is None:
        raise ApiError(401, "INVALID_TOKEN", "Session is invalid or expired.")
    try:
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (KeyError, ValueError):
        user = None
    if user is None or user.deleted_at is not None or user.status != UserStatus.active:
        raise ApiError(401, "INVALID_TOKEN", "Session is invalid or expired.")
    return user


def require_roles(*role_keys: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        user_roles = {r.key if hasattr(r.key, "value") else r.key for r in user.roles}
        if not (set(role_keys) & user_roles):
            raise ApiError(403, "FORBIDDEN", "You do not have permission to perform this action.")
        return user

    return dependency
