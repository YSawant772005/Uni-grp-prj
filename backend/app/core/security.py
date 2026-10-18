"""Password hashing and JWT handling.

Tokens are issued as HttpOnly cookies by the API layer (see routers/auth.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bool(pwd_context.verify(plain, hashed))
    except ValueError:
        return False


def _encode(sub: str, token_type: str, ttl: timedelta, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "type": token_type, "iat": now, "exp": now + ttl, **(extra or {})}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, roles: list[str]) -> str:
    return _encode(
        user_id,
        "access",
        timedelta(minutes=settings.jwt_access_ttl_minutes),
        {"roles": roles},
    )


def create_refresh_token(user_id: str) -> str:
    return _encode(user_id, "refresh", timedelta(days=settings.jwt_refresh_ttl_days))


def decode_token(token: str, expected_type: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == expected_type else None
