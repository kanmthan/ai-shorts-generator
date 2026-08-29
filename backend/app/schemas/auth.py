"""Pydantic v2 schemas for the authentication module.

Request/response models for ``/api/v1/auth/*``:

* :class:`RegisterRequest`      -> ``POST /register``
* :class:`LoginRequest`         -> ``POST /login``
* :class:`RefreshRequest`       -> ``POST /refresh`` / ``POST /logout``
* :class:`TokenPair`            -> login / refresh / OAuth callback response
* :class:`UserOut`              -> ``GET|PUT /me``, ``POST /register`` response
* :class:`UpdateProfileRequest` -> ``PUT /me``
* :class:`PasswordResetRequest` -> ``POST /password-reset``
* :class:`MessageResponse`      -> generic ``{"message": ...}`` envelope
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload for creating a local email/password account."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    """JSON payload for password login (not OAuth2 form data)."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenPair(BaseModel):
    """A freshly minted access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Payload carrying a refresh token (rotate on ``/refresh``, revoke on ``/logout``)."""

    refresh_token: str = Field(min_length=1)


class UserOut(BaseModel):
    """Public representation of a :class:`~app.models.user.User`."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    is_verified: bool
    oauth_provider: str | None = None
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    """Editable profile fields for ``PUT /me``."""

    full_name: str = Field(min_length=1, max_length=255)


class PasswordResetRequest(BaseModel):
    """Payload for requesting a password-reset email."""

    email: EmailStr


class MessageResponse(BaseModel):
    """Generic human-readable status envelope."""

    message: str
