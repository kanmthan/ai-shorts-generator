"""Rendering & Export: API routes + the ``render_short`` Celery task."""

from __future__ import annotations

import os

import pytest
from tests.conftest import (
    TestSessionLocal,
    make_broll,
    make_project,
    make_render_job,
    make_short,
    make_subtitle,
)

import app.tasks.render as render_mod
from app.exceptions import ExternalServiceError
from app.models import RenderJob, Short
from app.services import rendering, storage


@pytest.fixture
def short(db, user):
    project = make_project(db, user.id)
    return make_short(db, project.id, index=1, status="draft")


# --------------------------------------------------------------------------- #
# API                                                                         #
# --------------------------------------------------------------------------- #
def test_enqueue_render_returns_202(auth_client, celery_stub, short, db):
    resp = auth_client.post(f"/api/v1/shorts/{short.id}/render")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"

    celery_stub.render_delay.assert_called_once_with(body["job_id"])
    db.expire_all()
    assert db.get(Short, short.id).status == "queued"


def test_enqueue_render_conflicts_when_active(auth_client, celery_stub, short, db):
    make_render_job(db, short.id, short.project.user_id, status="processing")
    resp = auth_client.post(f"/api/v1/shorts/{short.id}/render")
    assert resp.status_code == 409
    celery_stub.render_delay.assert_not_called()


def test_get_render_job_is_per_user(auth_client, other_auth_client, short, db):
    job = make_render_job(db, short.id, short.project.user_id)
    assert auth_client.get(f"/api/v1/render-jobs/{job.id}").status_code == 200
    assert other_auth_client.get(f"/api/v1/render-jobs/{job.id}").status_code == 404


def test_list_render_jobs_scoped(auth_client, short, db):
    make_render_job(db, short.id, short.project.user_id)
    make_render_job(db, short.id, short.project.user_id, status="completed")
    rows = auth_client.get("/api/v1/render-jobs").json()
    assert len(rows) == 2


def test_cancel_render_job(auth_client, short, db):
    job = make_render_job(db, short.id, short.project.user_id, status="queued")
    resp = auth_client.post(f"/api/v1/render-jobs/{job.id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    db.expire_all()
    assert db.get(RenderJob, job.id).status == "cancelled"


def test_cancel_completed_job_conflicts(auth_client, short, db):
    job = make_render_job(db, short.id, short.project.user_id, status="completed")
    assert auth_client.post(f"/api/v1/render-jobs/{job.id}/cancel").status_code == 409


def test_download_before_ready_is_404(auth_client, short, db):
    job = make_render_job(db, short.id, short.project.user_id, status="processing")
    assert auth_client.get(f"/api/v1/render-jobs/{job.id}/download").status_code == 404


# --------------------------------------------------------------------------- #
# render_short task                                                           #
# --------------------------------------------------------------------------- #
@pytest.fixture
def stage_stubs(monkeypatch, tmp_path):
    """No-op every ffmpeg/yt-dlp stage + storage; capture the temp workdir."""
    captured: dict[str, str] = {}
    real_mkdtemp = render_mod.tempfile.mkdtemp

    def fake_mkdtemp(*args, **kwargs):
        path = real_mkdtemp(*args, **kwargs)
        captured["workdir"] = path
        return path

    monkeypatch.setattr(render_mod.tempfile, "mkdtemp", fake_mkdtemp)

    def _fake_file(name):
        def _stage(*args, **kwargs):
            path = tmp_path / name
            path.write_bytes(b"fake-mp4-bytes" * 64)
            return path

        return _stage

    monkeypatch.setattr(rendering, "download_source_segment", _fake_file("seg.mp4"))
    monkeypatch.setattr(rendering, "crop_vertical", _fake_file("vertical.mp4"))
    monkeypatch.setattr(rendering, "remove_silence", _fake_file("desilenced.mp4"))
    monkeypatch.setattr(rendering, "overlay_broll", _fake_file("broll.mp4"))
    monkeypatch.setattr(rendering, "burn_captions", _fake_file("captioned.mp4"))
    monkeypatch.setattr(rendering, "encode_final", _fake_file("final.mp4"))
    monkeypatch.setattr(storage, "store_output", lambda path, key: f"/media/{key}")
    return captured


def _run_job(db, user_id):
    project = make_project(db, user_id, url="https://youtu.be/abc")
    short = make_short(db, project.id, index=1)
    make_broll(db, short.id, asset_status="fetched", asset_url="https://cdn.example.com/a.mp4")
    make_subtitle(db, short.id)
    job = make_render_job(db, short.id, user_id, status="queued")
    return job


def test_render_short_walks_stages_to_completed(stage_stubs, db, user):
    job = _run_job(db, user.id)

    result = render_mod.render_short(job.id)
    assert result == {"render_job_id": job.id, "status": "completed"}

    fresh = TestSessionLocal()
    try:
        row = fresh.get(RenderJob, job.id)
        assert row.status == "completed"
        assert row.progress == 100
        assert row.stage is None
        assert row.output_url == f"/media/renders/{user.id}/{job.id}.mp4"
        assert row.resolution == "1080x1920"
        assert row.video_codec == "h264"
        assert row.audio_codec == "aac"
        assert row.aspect_ratio == "9:16"
        assert row.file_size_bytes and row.file_size_bytes > 0
        assert fresh.get(Short, row.short_id).status == "rendered"
    finally:
        fresh.close()

    assert not os.path.exists(stage_stubs["workdir"])  # temp workdir cleaned up


def test_render_short_stage_failure_marks_failed_and_cleans_up(stage_stubs, monkeypatch, db, user):
    job = _run_job(db, user.id)

    def _boom(*args, **kwargs):
        raise ExternalServiceError("ffmpeg crop stage failed")

    monkeypatch.setattr(rendering, "crop_vertical", _boom)

    result = render_mod.render_short(job.id)
    assert result["status"] == "failed"

    fresh = TestSessionLocal()
    try:
        row = fresh.get(RenderJob, job.id)
        assert row.status == "failed"
        assert "crop" in (row.error_message or "")
        assert fresh.get(Short, row.short_id).status == "failed"
    finally:
        fresh.close()

    assert not os.path.exists(stage_stubs["workdir"])


def test_render_short_missing_job_is_noop(stage_stubs):
    result = render_mod.render_short(555_555)
    assert result == {"render_job_id": 555_555, "status": "missing"}


def test_render_short_already_cancelled_short_circuits(stage_stubs, db, user):
    job = _run_job(db, user.id)
    job.status = "cancelled"
    db.commit()

    result = render_mod.render_short(job.id)
    assert result["status"] == "cancelled"
