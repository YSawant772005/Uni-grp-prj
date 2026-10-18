"""Account creation and authentication service."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import hash_password, verify_password
from app.models import Role, StudentProfile, User, UserStatus, UserRole


def role_keys(user: User) -> list[str]:
    return [r.key.value if hasattr(r.key, "value") else str(r.key) for r in user.roles]


def create_account(db: Session, *, email: str, password: str, display_name: str | None) -> User:
    normalized = email.strip().lower()
    if db.scalar(select(User).where(User.email == normalized)) is not None:
        raise ApiError(409, "EMAIL_TAKEN", "This email address is already registered.")
    user = User(
        email=normalized,
        password_hash=hash_password(password),
        display_name=display_name,
        status=UserStatus.active,
    )
    db.add(user)
    db.flush()
    student_role = db.scalar(select(Role).where(Role.key == "student"))
    if student_role is not None:
        db.add(UserRole(user_id=user.id, role_id=student_role.id))
    if db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id)) is None:
        db.add(StudentProfile(user_id=user.id))
    db.flush()
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    """Returns the user or raises a generic 401 (no account enumeration)."""
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized))
    if (
        user is None
        or user.status != UserStatus.active
        or not verify_password(password, user.password_hash)
    ):
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid email or password.")
    return user
