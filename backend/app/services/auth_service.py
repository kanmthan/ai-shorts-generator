"""Business logic for the authentication module.

Covers local email/password accounts, JWT session issuance with database-backed
refresh-token rotation, and Google OAuth account linking. Endpoints in
``app.routers.auth`` are thin wrappers around the functions defined here.

Error contract (all subclasses of :class:`app.exceptions.AppError`, rendered as
JSON by the global handlers):

* duplicate email on register -> :class:`~app.exceptions.ConflictError` (409)
* bad credentials / invalid or expired refresh token -> ``AuthError`` (401)
* empty profile field / unknown OAuth provider -> :class:`~app.exceptions.ValidationError` (422)

Passwords are only ever handled as bcrypt hashes (see ``app.auth.jwt``); no
plaintext password is logged or persisted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.dependencies import AuthError
from app.exceptions import ConflictError, ValidationError
from app.logging_config import get_logger
from app.models import OAUTH_PROVIDERS, RefreshToken, User
from app.schemas.auth import TokenPair, UpdateProfileRequest

logger = get_logger("auth_service")

__all__ = [
    "register_user",
    "authenticate_user",
    "issue_token_pair",
    "rotate_refresh_token",
    "revoke_refresh_token",
    "get_or_create_oauth_user",
    "update_profile",
    "get_user_by_email",
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _normalise_email(email: str) -> str:
    return email.strip().lower()


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(
        select(User).where(User.email == _normalise_email(email))
    ).scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return the user with this (case-insensitive) email, or ``None``."""
    return _get_user_by_email(db, email)


def _get_stored_refresh_token(db: Session, token: str) -> RefreshToken | None:
    return db.execute(
        select(RefreshToken).where(RefreshToken.token == token)
    ).scalar_one_or_none()


def _as_aware_utc(value: datetime) -> datetime:
    """Treat a naive DB timestamp as UTC so comparisons never raise."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


# --------------------------------------------------------------------------- #
# Registration & authentication
# --------------------------------------------------------------------------- #
def register_user(
    db: Session, *, email: str, password: str, full_name: str
) -> User:
    """Create a local email/password account.

    Raises:
        ConflictError: If an account already exists for ``email``.
    """
    email = _normalise_email(email)
    if _get_user_by_email(db, email) is not None:
        raise ConflictError("An account with this email already exists")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name.strip(),
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Registered user id=%s", user.id)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    """Verify an email/password pair and return the matching active user.

    Raises:
        AuthError: If the credentials are wrong or the account is disabled.
    """
    user = _get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        logger.info("Failed login for email=%s", _normalise_email(email))
        raise AuthError("Incorrect email or password")
    if not user.is_active:
        raise AuthError("This account is disabled")
    return user


# --------------------------------------------------------------------------- #
# Token issuance & rotation
# --------------------------------------------------------------------------- #
def issue_token_pair(db: Session, user: User) -> TokenPair:
    """Mint an access + refresh token pair and persist the refresh token row."""
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    db.add(
        RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            revoked=False,
        )
    )
    db.commit()
    logger.info("Issued token pair for user id=%s", user.id)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


def rotate_refresh_token(db: Session, refresh_token: str) -> TokenPair:
    """Validate a refresh token, revoke it, and issue a fresh token pair.

    Raises:
        AuthError: If the token is malformed, the wrong type, unknown, already
            revoked, expired, or its user is missing/inactive.
    """
    try:
        payload = decode_token(refresh_token)
    except Exception as exc:  # TokenError (AppError) or any jose failure
        raise AuthError("Invalid or expired refresh token") from exc

    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise AuthError("Wrong token type")

    stored = _get_stored_refresh_token(db, refresh_token)
    if stored is None or stored.revoked:
        raise AuthError("Refresh token is not valid")
    if _as_aware_utc(stored.expires_at) < datetime.now(UTC):
        raise AuthError("Refresh token has expired")

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthError("Invalid token subject") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")

    stored.revoked = True
    db.add(stored)
    db.commit()
    logger.info("Rotated refresh token id=%s for user id=%s", stored.id, user.id)
    return issue_token_pair(db, user)


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """Revoke a stored refresh token if present. Idempotent (logout never fails)."""
    stored = _get_stored_refresh_token(db, refresh_token)
    if stored is not None and not stored.revoked:
        stored.revoked = True
        db.add(stored)
        db.commit()
        logger.info("Revoked refresh token id=%s", stored.id)


# --------------------------------------------------------------------------- #
# OAuth
# --------------------------------------------------------------------------- #
def get_or_create_oauth_user(
    db: Session, *, email: str, full_name: str, provider: str
) -> User:
    """Return the user for an OAuth identity, creating/linking one as needed.

    Raises:
        ValidationError: If ``provider`` is not a supported OAuth provider.
    """
    if provider not in OAUTH_PROVIDERS:
        raise ValidationError(f"Unsupported OAuth provider: {provider}")

    email = _normalise_email(email)
    user = _get_user_by_email(db, email)
    if user is not None:
        dirty = False
        if not user.oauth_provider:
            user.oauth_provider = provider
            dirty = True
        if not user.is_verified:
            user.is_verified = True
            dirty = True
        if dirty:
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Linked %s OAuth to user id=%s", provider, user.id)
        return user

    fallback_name = email.split("@", 1)[0]
    user = User(
        email=email,
        hashed_password=None,
        full_name=(full_name or fallback_name).strip() or fallback_name,
        is_active=True,
        is_verified=True,
        oauth_provider=provider,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created %s OAuth user id=%s", provider, user.id)
    return user


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #
def update_profile(
    db: Session, user: User, data: UpdateProfileRequest
) -> User:
    """Apply an allowed profile update and return the refreshed user.

    Raises:
        ValidationError: If ``full_name`` is blank after trimming.
    """
    full_name = data.full_name.strip()
    if not full_name:
        raise ValidationError("full_name must not be empty")

    user.full_name = full_name
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Updated profile for user id=%s", user.id)
    return user
