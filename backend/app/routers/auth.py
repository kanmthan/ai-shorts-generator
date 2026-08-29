"""Authentication API routes (``/api/v1/auth``).

| Method | Path               | Response      | Notes                                   |
|--------|--------------------|---------------|-----------------------------------------|
| POST   | /register          | 201 UserOut   | local email/password signup (rate-limited) |
| POST   | /login             | TokenPair     | JSON body, not OAuth2 form (rate-limited)  |
| POST   | /refresh           | TokenPair     | rotate refresh token                    |
| POST   | /logout            | MessageResponse | revoke the supplied refresh token     |
| GET    | /me                | UserOut       | current user (Bearer access token)     |
| PUT    | /me                | UserOut       | update profile                         |
| POST   | /password-reset    | 200 MessageResponse | no account enumeration            |
| GET    | /google            | 307 redirect  | start Google OAuth with signed state   |
| GET    | /google/callback   | TokenPair     | verify state, exchange code            |
"""


from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

from app.auth.oauth import build_google_authorize_url, exchange_google_code
from app.config import settings
from app.dependencies import AuthError, CurrentUser, DbSession
from app.logging_config import get_logger
from app.models import User
from app.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UpdateProfileRequest,
    UserOut,
)
from app.services import auth_service

logger = get_logger("auth_router")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# --------------------------------------------------------------------------- #
# Rate limiting (slowapi)
# --------------------------------------------------------------------------- #
# ``limiter`` is defined here and consumed by ``app.main``. slowapi resolves the
# active limiter from ``request.app.state.limiter`` at call time, so the
# ``@limiter.limit(...)`` decorators below are inert until ``main.py`` wires it
# up. Add this to ``app/main.py`` -> ``create_app()`` (see the REPORT for exact
# line numbers):
#
#     from slowapi import _rate_limit_exceeded_handler
#     from slowapi.errors import RateLimitExceeded
#     from app.routers.auth import limiter as auth_limiter
#
#     app.state.limiter = auth_limiter
#     app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
#

# --------------------------------------------------------------------------- #
# Google OAuth anti-CSRF state (short-lived HS256 JWT signed with SECRET_KEY)
# --------------------------------------------------------------------------- #
_OAUTH_STATE_PURPOSE = "google_oauth_state"
_OAUTH_STATE_TTL_SECONDS = 600


def _sign_oauth_state() -> str:
    """Return a signed, expiring opaque ``state`` value for the Google redirect."""
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "purpose": _OAUTH_STATE_PURPOSE,
            "nonce": uuid4().hex,
            "iat": now,
            "exp": now + timedelta(seconds=_OAUTH_STATE_TTL_SECONDS),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _verify_oauth_state(state: str) -> None:
    """Validate a ``state`` value echoed back by Google.

    Raises:
        AuthError: If the state is missing, tampered with, expired, or not an
            OAuth-state token.
    """
    try:
        payload = jwt.decode(
            state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError as exc:
        raise AuthError("Invalid or expired OAuth state") from exc
    if payload.get("purpose") != _OAUTH_STATE_PURPOSE:
        raise AuthError("Invalid OAuth state")


# --------------------------------------------------------------------------- #
# Local email / password
# --------------------------------------------------------------------------- #
@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: RegisterRequest,
    db: DbSession,
) -> User:
    """Create a local email/password account."""
    return auth_service.register_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    db: DbSession,
) -> TokenPair:
    """Exchange email/password for an access + refresh token pair."""
    user = auth_service.authenticate_user(
        db, email=payload.email, password=payload.password
    )
    return auth_service.issue_token_pair(db, user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    """Rotate a refresh token: the old one is revoked, a new pair is returned."""
    return auth_service.rotate_refresh_token(db, payload.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: RefreshRequest, db: DbSession) -> MessageResponse:
    """Revoke the supplied refresh token. Always succeeds (idempotent)."""
    auth_service.revoke_refresh_token(db, payload.refresh_token)
    return MessageResponse(message="Signed out")


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #
@router.get("/me", response_model=UserOut)
async def read_me(current_user: CurrentUser) -> User:
    """Return the authenticated user's profile."""
    return current_user


@router.put("/me", response_model=UserOut)
async def update_me(
    payload: UpdateProfileRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> User:
    """Update the authenticated user's profile."""
    return auth_service.update_profile(db, current_user, payload)


@router.post("/password-reset", response_model=MessageResponse)
async def password_reset(
    payload: PasswordResetRequest,
    db: DbSession,
) -> MessageResponse:
    """Begin a password reset. Always 200 - never reveals whether the email exists."""
    user = auth_service.get_user_by_email(db, payload.email)
    if user is not None:
        logger.info("Password reset requested for user id=%s", user.id)
        # TODO: enqueue a transactional email with a signed, single-use reset link.
    else:
        logger.info("Password reset requested for unknown email")
    return MessageResponse(
        message="If an account exists for that email, a reset link has been sent."
    )


# --------------------------------------------------------------------------- #
# Google OAuth
# --------------------------------------------------------------------------- #
@router.get("/google")
async def google_login() -> RedirectResponse:
    """Redirect the browser to Google's consent screen with a signed ``state``."""
    url = build_google_authorize_url(_sign_oauth_state())
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/google/callback", response_model=TokenPair)
async def google_callback(
    state: str,
    code: str,
    db: DbSession,
) -> TokenPair:
    """Handle Google's redirect: verify ``state``, exchange ``code``, issue tokens."""
    _verify_oauth_state(state)
    profile = await exchange_google_code(code)
    user = auth_service.get_or_create_oauth_user(
        db, email=profile.email, full_name=profile.name, provider="google"
    )
    return auth_service.issue_token_pair(db, user)
