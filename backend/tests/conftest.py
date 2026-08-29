"""Shared pytest fixtures for the AI Shorts Generator backend test suite.

Everything external is mocked: no network, no ffmpeg, no yt-dlp, no Anthropic /
Pexels / Pixabay calls, and no Celery broker. The database is an in-memory
SQLite instance shared through a ``StaticPool`` (so the FastAPI request thread
and the test thread see the same rows).
"""

from __future__ import annotations

import os
import tempfile

# --- Environment must be set before *any* app import (Settings() reads it). ----
_MEDIA_ROOT = tempfile.mkdtemp(prefix="test-media-")
# File-based SQLite (not ":memory:"): the FastAPI request thread, the test
# thread and task-owned ``SessionLocal()`` connections must all see the same
# tables, and an in-memory DB is torn down the moment its last connection drops.
_DB_FD, _DB_PATH = tempfile.mkstemp(prefix="test-db-", suffix=".sqlite")
os.close(_DB_FD)
_DB_URL = f"sqlite:///{_DB_PATH}"
os.environ["DATABASE_URL"] = _DB_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("ANTHROPIC_MODEL", "claude-sonnet-5")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("PEXELS_API_KEY", "")
os.environ.setdefault("PIXABAY_API_KEY", "")
os.environ["MEDIA_ROOT"] = _MEDIA_ROOT

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as _db_mod
from app.config import settings
from app.database import Base, get_db
from app.main import app

# Import every model so ``Base.metadata`` is fully populated before create_all.
from app.models import (  # noqa: F401
    BrollSegment,
    Project,
    RefreshToken,
    RenderJob,
    Short,
    SubtitleSegment,
    User,
)

# --------------------------------------------------------------------------- #
# Engine / session                                                            #
# --------------------------------------------------------------------------- #
engine = create_engine(
    _DB_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    poolclass=StaticPool,
    future=True,
)
TestSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


# --------------------------------------------------------------------------- #
# Autouse fixtures                                                            #
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _settings_env(monkeypatch):
    """Force required settings onto the shared ``settings`` singleton."""
    monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key", raising=False)
    monkeypatch.setattr(settings, "ALGORITHM", "HS256", raising=False)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-anthropic-key", raising=False)
    monkeypatch.setattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-5", raising=False)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id", raising=False)
    monkeypatch.setattr(
        settings, "GOOGLE_CLIENT_SECRET", "test-google-client-secret", raising=False
    )
    monkeypatch.setattr(
        settings,
        "GOOGLE_REDIRECT_URI",
        "http://testserver/api/v1/auth/google/callback",
        raising=False,
    )
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "", raising=False)
    monkeypatch.setattr(settings, "PIXABAY_API_KEY", "", raising=False)
    monkeypatch.setattr(settings, "MEDIA_ROOT", _MEDIA_ROOT, raising=False)

    from app.rate_limit import limiter

    monkeypatch.setattr(limiter, "enabled", False, raising=False)


# Schema is created ONCE for the whole session on the shared file DB.
Base.metadata.create_all(bind=engine)


def pytest_sessionfinish(session, exitstatus):
    """Dispose the engine and remove the temp DB file at the end of the run."""
    import contextlib

    engine.dispose()
    with contextlib.suppress(OSError):
        os.unlink(_DB_PATH)


@pytest.fixture(autouse=True)
def _patch_session_local(monkeypatch):
    """Route every task-owned ``SessionLocal`` and ``get_db`` to the test engine.

    ``engine`` uses a ``StaticPool`` over one file DB, so the test thread, the
    TestClient worker thread and task-owned ``SessionLocal()`` calls all share a
    single connection and see each other's committed rows.
    """
    import app.tasks.analyze as analyze_mod
    import app.tasks.ingest as ingest_mod
    import app.tasks.render as render_mod

    for mod in (ingest_mod, analyze_mod, render_mod, _db_mod):
        monkeypatch.setattr(mod, "SessionLocal", TestSessionLocal, raising=False)

    def _get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _wipe_rows():
    """Delete every row after each test; the schema is created once per session."""
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture(autouse=True)
def _stub_dns(monkeypatch):
    """Deterministic, offline DNS for the SSRF guard."""
    import socket as _socket

    import app.services.url_guard as url_guard

    def fake_getaddrinfo(host, port, *args, **kwargs):
        h = (host or "").lower()
        if h in ("localhost", "localhost.localdomain"):
            ip = "127.0.0.1"
        elif any(tok in h for tok in ("internal", "private", "metadata", "corp", "intranet")):
            ip = "10.1.2.3"
        else:
            ip = "93.184.216.34"  # example.com - globally routable
        return [(_socket.AF_INET, _socket.SOCK_STREAM, 6, "", (ip, port or 0))]

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", fake_getaddrinfo)


@pytest.fixture(autouse=True)
def celery_stub(monkeypatch):
    """Replace every Celery enqueue call with a Mock (no broker in tests)."""
    from app.tasks.analyze import analyze_project, refetch_short_broll
    from app.tasks.celery_app import celery_app
    from app.tasks.ingest import ingest_project
    from app.tasks.render import render_short

    stub = SimpleNamespace(
        ingest_delay=Mock(name="ingest_project.delay"),
        ingest_apply_async=Mock(name="ingest_project.apply_async"),
        render_delay=Mock(name="render_short.delay"),
        analyze_delay=Mock(name="analyze_project.delay"),
        refetch_delay=Mock(name="refetch_short_broll.delay"),
        send_task=Mock(
            name="celery_app.send_task",
            return_value=SimpleNamespace(id="test-task-id"),
        ),
    )
    monkeypatch.setattr(ingest_project, "delay", stub.ingest_delay, raising=False)
    monkeypatch.setattr(
        ingest_project, "apply_async", stub.ingest_apply_async, raising=False
    )
    monkeypatch.setattr(render_short, "delay", stub.render_delay, raising=False)
    monkeypatch.setattr(analyze_project, "delay", stub.analyze_delay, raising=False)
    monkeypatch.setattr(refetch_short_broll, "delay", stub.refetch_delay, raising=False)
    monkeypatch.setattr(celery_app, "send_task", stub.send_task, raising=False)
    return stub


# --------------------------------------------------------------------------- #
# DB session + clients                                                        #
# --------------------------------------------------------------------------- #
@pytest.fixture
def db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _register_and_login(
    test_client: TestClient,
    email: str,
    password: str = "password123",
    full_name: str = "Test User",
) -> SimpleNamespace:
    resp = test_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["id"]

    resp = test_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return SimpleNamespace(
        id=user_id,
        email=email,
        password=password,
        full_name=full_name,
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )


@pytest.fixture
def user(client):
    return _register_and_login(client, "user@example.com")


@pytest.fixture
def other_user(client):
    return _register_and_login(client, "other@example.com", full_name="Other User")


@pytest.fixture
def auth_client(user):
    test_client = TestClient(app)
    test_client.headers.update(user.headers)
    return test_client


@pytest.fixture
def other_auth_client(other_user):
    test_client = TestClient(app)
    test_client.headers.update(other_user.headers)
    return test_client


# --------------------------------------------------------------------------- #
# Data factories                                                              #
# --------------------------------------------------------------------------- #
_DEFAULT_SCORES = {
    "hook_strength": 8.0,
    "standalone_value": 7.0,
    "engagement": 9.0,
    "retention": 7.5,
    "payoff": 8.0,
    "clarity": 8.5,
    "shareability": 7.0,
    "viral_potential": 8.0,
    "b_roll_quality": 6.5,
    "overall": 7.8,
}


def make_project(db, user_id: int, **kw) -> Project:
    defaults = dict(
        user_id=user_id,
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        platform="youtube",
        external_id="dQw4w9WgXcQ",
        title="A Long Form Video",
        duration_seconds=1200,
        thumbnail_url="https://img.example.com/t.jpg",
        status="ready",
        language="en",
    )
    defaults.update(kw)
    project = Project(**defaults)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def make_short(db, project_id: int, index: int = 1, **kw) -> Short:
    defaults = dict(
        project_id=project_id,
        index=index,
        start_time="00:01:00",
        end_time="00:01:45",
        duration_seconds=45.0,
        title=f"Short {index}",
        hook="You won't believe this",
        summary="A compelling standalone moment.",
        reason="High energy and a clear payoff.",
        scores=dict(_DEFAULT_SCORES),
        caption="Watch this clip!",
        hashtags=["#shorts", "#viral"],
        editing={},
        category="viral",
        status="draft",
    )
    defaults.update(kw)
    short = Short(**defaults)
    db.add(short)
    db.commit()
    db.refresh(short)
    return short


def make_broll(db, short_id: int, **kw) -> BrollSegment:
    defaults = dict(
        short_id=short_id,
        start="00:15",
        end="00:25",
        original_start="01:15",
        original_end="01:25",
        duration_seconds=10.0,
        description="Aerial city shot",
        reason="Illustrates the point",
        search_keywords=["city", "aerial"],
        type="stock_video",
        transition="smooth_cut",
        placement="middle",
        use_broll=True,
        asset_status="pending",
    )
    defaults.update(kw)
    seg = BrollSegment(**defaults)
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return seg


def make_subtitle(db, short_id: int, **kw) -> SubtitleSegment:
    defaults = dict(
        short_id=short_id,
        start="00:00",
        end="00:03",
        text="Hello world",
        highlight_words=["Hello"],
    )
    defaults.update(kw)
    seg = SubtitleSegment(**defaults)
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return seg


def make_render_job(db, short_id: int, user_id: int, **kw) -> RenderJob:
    defaults = dict(short_id=short_id, user_id=user_id, status="queued", progress=0)
    defaults.update(kw)
    job = RenderJob(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.fixture
def factories():
    """Expose the data factories as a single fixture object."""
    return SimpleNamespace(
        project=make_project,
        short=make_short,
        broll=make_broll,
        subtitle=make_subtitle,
        render_job=make_render_job,
        scores=lambda **kw: {**_DEFAULT_SCORES, **kw},
    )
