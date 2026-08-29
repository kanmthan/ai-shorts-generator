"""Password hashing and JWT token helpers for the auth module.

Phase 1 already implements ``get_current_user`` in ``app.dependencies`` (it
decodes the Bearer *access* token directly with :mod:`jose`). This module only
adds the token *minting* helpers and password hashing that the auth service and
router rely on.

Note on bcrypt: the pinned ``passlib`` release is not compatible with
``bcrypt>=5`` (its backend probe raises at import time), so we call the
``bcrypt`` package directly. The public helpers keep the classic
``hash_password`` / ``verify_password`` names.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
from fastapi import status
from jose import JWTError, jwt

from app.config import settings
from app.exceptions import AppError
from app.logging_config import get_logger

logger = get_logger("auth.jwt")

__all__ = [
    "TokenError",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
]

# bcrypt only considers the first 72 bytes of a secret and raises on longer
# input, so we truncate deterministically before hashing/verifying.
_BCRYPT_MAX_BYTES = 72

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class TokenError(AppError):
    """A JWT could not be decoded, was expired, or had the wrong type (HTTP 401)."""

    code = "INVALID_TOKEN"
    status_code = status.HTTP_401_UNAUTHORIZED


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Return a salted bcrypt hash for ``password``."""
    secret = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(secret, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Return ``True`` when ``plain_password`` matches ``hashed_password``."""
    if not hashed_password:
        return False
    secret = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(secret, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# JWT helpers
# --------------------------------------------------------------------------- #
def _encode(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(sub: str, extra: dict[str, Any] | None = None) -> str:
    """Mint a short-lived access token for ``sub`` (usually the user id)."""
    return _encode(
        sub,
        ACCESS_TOKEN_TYPE,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra,
    )


def create_refresh_token(sub: str) -> str:
    """Mint a long-lived refresh token for ``sub``."""
    return _encode(
        sub,
        REFRESH_TOKEN_TYPE,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, returning its claims.

    Raises:
        TokenError: If the token is malformed, has a bad signature, or expired.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        logger.info("JWT decode failed: %s", exc)
        raise TokenError("Invalid or expired token") from exc
