"""Shorts Analysis API routes (shorts seeded directly in the DB)."""

from __future__ import annotations

import pytest
from tests.conftest import make_broll, make_project, make_short, make_subtitle

from app.models import Short
from app.schemas.export import ShortsExportEnvelope


@pytest.fixture
def project_with_shorts(db, user):
    project = make_project(db, user.id, duration_seconds=1200)
    shorts = []
    for i in range(1, 6):
        short = make_short(db, project.id, index=i, title=f"Short {i}")
        make_broll(db, short.id)
        make_subtitle(db, short.id)
        shorts.append(short)
    return project, shorts


def test_list_shorts_returns_cards(auth_client, project_with_shorts):
    project, shorts = project_with_shorts
    resp = auth_client.get(f"/api/v1/projects/{project.id}/shorts")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 5
    first = body[0]
    assert first["index"] == 1
    assert first["overall_score"] == pytest.approx(7.8)
    assert first["engagement_score"] == pytest.approx(9.0)
    assert first["broll_timeline"]


def test_list_shorts_foreign_project_404(other_auth_client, project_with_shorts):
    project, _ = project_with_shorts
    assert other_auth_client.get(f"/api/v1/projects/{project.id}/shorts").status_code == 404


def test_get_short_full_detail(auth_client, project_with_shorts):
    _, shorts = project_with_shorts
    resp = auth_client.get(f"/api/v1/shorts/{shorts[0].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == shorts[0].id
    assert len(body["broll_segments"]) == 1
    assert len(body["subtitle_segments"]) == 1
    assert body["scores"]["overall"] == pytest.approx(7.8)


def test_get_short_foreign_404(other_auth_client, project_with_shorts):
    _, shorts = project_with_shorts
    assert other_auth_client.get(f"/api/v1/shorts/{shorts[0].id}").status_code == 404


def test_patch_short_trim_updates_duration(auth_client, project_with_shorts, db):
    _, shorts = project_with_shorts
    resp = auth_client.patch(
        f"/api/v1/shorts/{shorts[0].id}",
        json={"start_time": "00:00:10", "end_time": "00:00:52", "title": "Trimmed"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Trimmed"
    assert body["duration_seconds"] == pytest.approx(42.0)

    db.expire_all()
    assert db.get(Short, shorts[0].id).duration_seconds == pytest.approx(42.0)


def test_patch_short_rejects_unknown_field(auth_client, project_with_shorts):
    _, shorts = project_with_shorts
    resp = auth_client.patch(f"/api/v1/shorts/{shorts[0].id}", json={"nope": 1})
    assert resp.status_code == 422


def test_delete_short(auth_client, project_with_shorts, db):
    _, shorts = project_with_shorts
    target = shorts[2].id
    assert auth_client.delete(f"/api/v1/shorts/{target}").status_code == 204
    db.expunge_all()
    assert db.get(Short, target) is None


def test_regenerate_enqueues_analysis(auth_client, project_with_shorts, celery_stub, db):
    project, _ = project_with_shorts
    resp = auth_client.post(f"/api/v1/projects/{project.id}/shorts/regenerate")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "analyzing"
    assert body["task_id"] == "test-task-id"

    celery_stub.send_task.assert_called_once()
    args, kwargs = celery_stub.send_task.call_args
    assert args[0] == "app.tasks.analyze.analyze_project"
    assert kwargs["args"] == [project.id]

    db.expire_all()
    from app.models import Project

    assert db.get(Project, project.id).status == "analyzing"


def test_refetch_broll_enqueues(auth_client, project_with_shorts, celery_stub):
    _, shorts = project_with_shorts
    resp = auth_client.post(f"/api/v1/shorts/{shorts[0].id}/broll/refetch")
    assert resp.status_code == 202
    args, kwargs = celery_stub.send_task.call_args
    assert args[0] == "app.tasks.analyze.refetch_short_broll"


# --------------------------------------------------------------------------- #
# export.json master-format contract                                          #
# --------------------------------------------------------------------------- #
def test_export_json_success_envelope(auth_client, project_with_shorts):
    _, shorts = project_with_shorts
    resp = auth_client.get(f"/api/v1/shorts/{shorts[0].id}/export.json")
    assert resp.status_code == 200

    envelope = ShortsExportEnvelope.model_validate(resp.json())
    assert envelope.status == "success"  # project has >= 5 shorts
    assert envelope.total_shorts == 1
    assert len(envelope.shorts) == 1
    exported = envelope.shorts[0]
    assert exported.id == "short_1"
    assert exported.broll_segments  # min_length 1 enforced by schema
    assert exported.scores.overall == pytest.approx(7.8)


def test_export_json_partial_when_few_shorts(auth_client, db, user):
    project = make_project(db, user.id, duration_seconds=600)
    short = make_short(db, project.id, index=1)
    make_subtitle(db, short.id)

    resp = auth_client.get(f"/api/v1/shorts/{short.id}/export.json")
    assert resp.status_code == 200
    envelope = ShortsExportEnvelope.model_validate(resp.json())
    assert envelope.status == "partial"
    # short with no B-roll rows still exports a synthetic use_broll=False segment
    assert envelope.shorts[0].broll_segments[0].use_broll is False


def test_export_json_foreign_404(other_auth_client, project_with_shorts):
    _, shorts = project_with_shorts
    assert other_auth_client.get(f"/api/v1/shorts/{shorts[0].id}/export.json").status_code == 404
