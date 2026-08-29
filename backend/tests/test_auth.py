"""Authentication module: register / login / refresh / logout / profile / Google."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.auth.oauth import GoogleUserInfo
from app.routers import auth as auth_router

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


def _register(client, email="new@example.com", password="password123", full_name="New User"):
    return client.post(
        REGISTER, json={"email": email, "password": password, "full_name": full_name}
    )


# --------------------------------------------------------------------------- #
# Register                                                                    #
# --------------------------------------------------------------------------- #
def test_register_returns_201_and_user(client):
    resp = _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert body["full_name"] == "New User"
    assert body["is_active"] is True
    assert "hashed_password" not in body


def test_register_duplicate_email_conflict(client):
    assert _register(client).status_code == 201
    resp = _register(client)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_register_rejects_short_password(client):
    resp = _register(client, password="short")
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Login                                                                       #
# --------------------------------------------------------------------------- #
def test_login_returns_token_pair(client):
    _register(client)
    resp = client.post(LOGIN, json={"email": "new@example.com", "password": "password123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_bad_credentials_401(client):
    _register(client)
    resp = client.post(LOGIN, json={"email": "new@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_user_401(client):
    resp = client.post(LOGIN, json={"email": "ghost@example.com", "password": "password123"})
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# /auth/me                                                                    #
# --------------------------------------------------------------------------- #
def test_me_requires_token(client):
    assert client.get(ME).status_code == 401


def test_me_with_token(auth_client, user):
    resp = auth_client.get(ME)
    assert resp.status_code == 200
    assert resp.json()["email"] == user.email


def test_me_rejects_garbage_token(client):
    resp = client.get(ME, headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_update_profile(auth_client):
    resp = auth_client.put(ME, json={"full_name": "Renamed Person"})
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Renamed Person"
    assert auth_client.get(ME).json()["full_name"] == "Renamed Person"


def test_update_profile_rejects_blank_name(auth_client):
    resp = auth_client.put(ME, json={"full_name": "   "})
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Refresh rotation + logout                                                   #
# --------------------------------------------------------------------------- #
def test_refresh_rotates_and_revokes_old(client, user):
    first = client.post(REFRESH, json={"refresh_token": user.refresh_token})
    assert first.status_code == 200
    rotated = first.json()["refresh_token"]
    assert rotated != user.refresh_token

    # Re-using the original (now revoked) refresh token must fail.
    replay = client.post(REFRESH, json={"refresh_token": user.refresh_token})
    assert replay.status_code == 401

    # The freshly issued token still works.
    assert client.post(REFRESH, json={"refresh_token": rotated}).status_code == 200


def test_logout_revokes_refresh_token(client, user):
    resp = client.post(LOGOUT, json={"refresh_token": user.refresh_token})
    assert resp.status_code == 200
    assert resp.json()["message"]

    assert client.post(REFRESH, json={"refresh_token": user.refresh_token}).status_code == 401


def test_logout_is_idempotent(client, user):
    assert client.post(LOGOUT, json={"refresh_token": user.refresh_token}).status_code == 200
    assert client.post(LOGOUT, json={"refresh_token": user.refresh_token}).status_code == 200


def test_refresh_with_access_token_rejected(client, user):
    resp = client.post(REFRESH, json={"refresh_token": user.access_token})
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Google OAuth                                                                 #
# --------------------------------------------------------------------------- #
def test_google_login_redirects(client):
    resp = client.get("/api/v1/auth/google", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].startswith("https://accounts.google.com/")


def test_google_callback_bad_state_is_4xx(client, monkeypatch):
    monkeypatch.setattr(
        auth_router,
        "exchange_google_code",
        AsyncMock(return_value=GoogleUserInfo(email="x@y.com", name="X", sub="1")),
    )
    resp = client.get(
        "/api/v1/auth/google/callback",
        params={"state": "tampered-state", "code": "abc"},
        follow_redirects=False,
    )
    assert 400 <= resp.status_code < 500


def test_google_callback_happy_path(client, monkeypatch):
    monkeypatch.setattr(
        auth_router,
        "exchange_google_code",
        AsyncMock(
            return_value=GoogleUserInfo(
                email="oauth-user@example.com", name="OAuth User", sub="google-123"
            )
        ),
    )
    state = auth_router._sign_oauth_state()
    resp = client.get(
        "/api/v1/auth/google/callback",
        params={"state": state, "code": "valid-code"},
        follow_redirects=False,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]


@pytest.mark.parametrize("missing", ["state", "code"])
def test_google_callback_requires_params(client, missing):
    params = {"state": "s", "code": "c"}
    params.pop(missing)
    resp = client.get("/api/v1/auth/google/callback", params=params, follow_redirects=False)
    assert resp.status_code == 422
