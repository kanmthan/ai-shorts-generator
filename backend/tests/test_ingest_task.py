"""``app.tasks.ingest.ingest_project`` - metadata + transcript pipeline stage."""

from __future__ import annotations

import pytest
from tests.conftest import TestSessionLocal, make_project

import app.tasks.ingest as ingest_mod
from app.exceptions import ExternalServiceError
from app.models import Project
from app.services.ingestion import VideoMeta

_META = VideoMeta(
    url="https://youtu.be/abc",
    video_id="abc123",
    title="Ingested Title",
    duration_seconds=900,
    platform="youtube",
    thumbnail_url="https://img.example.com/x.jpg",
)
_TRANSCRIPT = [
    {"start": 0.0, "end": 2.0, "text": "hello there"},
    {"start": 2.0, "end": 4.0, "text": "second line"},
]


@pytest.fixture
def _seeded_user(client):
    from tests.conftest import _register_and_login

    return _register_and_login(client, "ingest@example.com")


def test_ingest_success_advances_to_analyzing(monkeypatch, db, celery_stub, _seeded_user):
    project = make_project(db, _seeded_user.id, status="pending", title=None, duration_seconds=None)

    monkeypatch.setattr(ingest_mod, "fetch_metadata", lambda url: _META)
    monkeypatch.setattr(
        ingest_mod, "fetch_transcript", lambda url, vid, platform: list(_TRANSCRIPT)
    )

    result = ingest_mod.ingest_project(project.id)

    assert result == {"project_id": project.id, "status": "analyzing"}
    celery_stub.send_task.assert_called_once()
    args, kwargs = celery_stub.send_task.call_args
    assert args[0] == "app.tasks.analyze.analyze_project"
    assert kwargs["args"] == [project.id]

    fresh = TestSessionLocal()
    try:
        row = fresh.get(Project, project.id)
        assert row.status == "analyzing"
        assert row.title == "Ingested Title"
        assert row.duration_seconds == 900
        assert row.external_id == "abc123"
        assert row.transcript == _TRANSCRIPT
        assert row.error_message is None
    finally:
        fresh.close()


def test_ingest_no_captions_marks_failed(monkeypatch, db, celery_stub, _seeded_user):
    project = make_project(db, _seeded_user.id, status="pending")

    monkeypatch.setattr(ingest_mod, "fetch_metadata", lambda url: _META)

    def _no_captions(url, vid, platform):
        raise ExternalServiceError("No captions available for this video")

    monkeypatch.setattr(ingest_mod, "fetch_transcript", _no_captions)

    result = ingest_mod.ingest_project(project.id)

    assert result["status"] == "failed"
    celery_stub.send_task.assert_not_called()

    fresh = TestSessionLocal()
    try:
        row = fresh.get(Project, project.id)
        assert row.status == "failed"
        assert "captions" in (row.error_message or "").lower()
    finally:
        fresh.close()


def test_ingest_metadata_failure_marks_failed(monkeypatch, db, celery_stub, _seeded_user):
    project = make_project(db, _seeded_user.id, status="pending")

    def _boom(url):
        raise ExternalServiceError("Could not read video metadata")

    monkeypatch.setattr(ingest_mod, "fetch_metadata", _boom)

    result = ingest_mod.ingest_project(project.id)
    assert result["status"] == "failed"

    fresh = TestSessionLocal()
    try:
        assert fresh.get(Project, project.id).status == "failed"
    finally:
        fresh.close()


def test_ingest_missing_project_is_noop(monkeypatch, celery_stub):
    result = ingest_mod.ingest_project(999_999)
    assert result == {"project_id": 999_999, "status": "missing"}
    celery_stub.send_task.assert_not_called()
