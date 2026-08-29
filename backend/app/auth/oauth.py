"""Google OAuth 2.0 helpers (Authlib + httpx).

``build_google_authorize_url`` produces the redirect target for the "Sign in with
Google" button; ``exchange_google_code`` swaps the authorization ``code`` Google
returns for the user's profile. All network I/O goes through Authlib's async
httpx client. Client secrets are never logged.
"""

from __future__ import annotations

from dataclasses import dataclass

from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.config import settings
from app.exceptions import ExternalServiceError, ValidationError
from app.logging_config import get_logger

logger = get_logger("auth.oauth")

__all__ = ["GoogleUserInfo", "build_google_authorize_url", "exchange_google_code"]

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPE = "openid email profile"


@dataclass(frozen=True)
class GoogleUserInfo:
    """The subset of the Google profile the auth service needs."""

    email: str
    name: str
    sub: str


def _require_config() -> None:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise ValidationError("Google OAuth is not configured")


def _client() -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
        scope=GOOGLE_SCOPE,
    )


def build_google_authorize_url(state: str) -> str:
    """Return the Google consent-screen URL to redirect the browser to.

    Args:
        state: An opaque, signed anti-CSRF value echoed back to the callback.
    """
    _require_config()
    url, _ = _client().create_authorization_url(
        GOOGLE_AUTH_ENDPOINT,
        state=state,
        access_type="offline",
        prompt="consent",
    )
    return url


async def exchange_google_code(code: str) -> GoogleUserInfo:
    """Exchange an authorization ``code`` for the signed-in Google user's profile.

    Raises:
        ValidationError: If Google OAuth is not configured.
        ExternalServiceError: If the token exchange or userinfo call fails.
    """
    _require_config()
    try:
        async with _client() as client:
            await client.fetch_token(
                GOOGLE_TOKEN_ENDPOINT,
                code=code,
                grant_type="authorization_code",
            )
            response = await client.get(GOOGLE_USERINFO_ENDPOINT)
            response.raise_for_status()
            data: dict[str, object] = response.json()
    except (ValidationError, ExternalServiceError):
        raise
    except Exception as exc:  # network error, bad code, non-2xx, bad JSON
        logger.warning("Google OAuth exchange failed: %s", exc.__class__.__name__)
        raise ExternalServiceError("Failed to complete Google sign-in") from exc

    email = str(data.get("email") or "").strip().lower()
    sub = str(data.get("sub") or "").strip()
    if not email or not sub:
        raise ExternalServiceError("Google did not return an email address")
    name = str(data.get("name") or "").strip() or email.split("@", 1)[0]
    return GoogleUserInfo(email=email, name=name, sub=sub)
