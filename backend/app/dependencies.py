"""Shared FastAPI dependencies.

Re-exports the DB session dependency (owned by DATABASE-AGENT in
``app.database``) and provides JWT-based current-user resolution.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.exceptions import AppError
from app.logging_config import get_logger
from app.models import User

logger = get_logger("dependencies")

__all__ = [
    "get_db",
    "get_current_user",
    "get_current_user_optional",
    "DbSession",
    "CurrentUser",
    "OptionalCurrentUser",
]

# ``auto_error=False`` so we can return ``None`` for the optional variant.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


class AuthError(AppError):
    """Authentication failed (HTTP 401)."""

    code = "UNAUTHORIZED"
    status_code = status.HTTP_401_UNAUTHORIZED


def _decode_subject(token: str) -> str:
    """Decode a Bearer access token and return its ``sub`` claim.

    Raises:
        AuthError: If the token is missing, malformed, expired, or not an
            ``access`` token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:  # expired, bad signature, malformed
        logger.info("JWT decode failed: %s", exc)
        raise AuthError("Invalid or expired token") from exc

    if payload.get("type") != "access":
        raise AuthError("Wrong token type")

    subject = payload.get("sub")
    if not subject:
        raise AuthError("Token missing subject")
    return str(subject)


def _load_user(db: Session, user_id: str) -> User:
    """Load an active user by primary key or raise ``AuthError``."""
    try:
        pk = int(user_id)
    except (TypeError, ValueError) as exc:
        raise AuthError("Invalid token subject") from exc

    user = db.query(User).filter(User.id == pk).first()
    if user is None or not getattr(user, "is_active", True):
        raise AuthError("User not found or inactive")
    return user


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the authenticated :class:`User` from the ``Authorization`` header.

    Raises:
        AuthError: 401 when no valid Bearer token / user is present.
    """
    if not token:
        raise AuthError("Not authenticated")
    subject = _decode_subject(token)
    return _load_user(db, subject)


async def get_current_user_optional(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Like :func:`get_current_user` but returns ``None`` when unauthenticated."""
    if not token:
        return None
    try:
        subject = _decode_subject(token)
        return _load_user(db, subject)
    except AppError:
        return None


# Convenient annotated aliases for routers (Phase 2).
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalCurrentUser = Annotated["User | None", Depends(get_current_user_optional)]


def get_client_ip(request: Request) -> str:
    """Best-effort client IP for rate limiting / audit logs."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
