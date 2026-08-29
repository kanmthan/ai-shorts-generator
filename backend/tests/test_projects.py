"""Projects & Video Ingestion API routes."""

from __future__ import annotations

import pytest
from tests.conftest import make_project

from app.models import Project

PROJECTS = "/api/v1/projects"
GOOD_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


# --------------------------------------------------------------------------- #
# Create + enqueue                                                            #
# --------------------------------------------------------------------------- #
def test_create_project_enqueues_ingestion(auth_client, celery_stub, db, user):
    resp = auth_client.post(PROJECTS, json={"url": GOOD_URL})
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["user_id"] == user.id

    celery_stub.ingest_delay.assert_called_once()
    (enqueued_id,) = celery_stub.ingest_delay.call_args.args
    assert enqueued_id == body["id"]

    row = db.get(Project, body["id"])
    assert row is not None and row.status == "pending"


def test_create_project_requires_auth(client):
    assert client.post(PROJECTS, json={"url": GOOD_URL}).status_code == 401


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://169.254.169.254/latest/meta-data/",  # raw link-local IP literal
        "http://localhost/video",  # resolves to loopback
        "http://10.0.0.10/video",  # raw private IP literal
        "http://internal-metadata.example.com/video",  # hostname -> private IP
        "ftp://example.com/video.mp4",  # disallowed scheme
    ],
)
def test_create_project_ssrf_rejected(auth_client, celery_stub, bad_url):
    resp = auth_client.post(PROJECTS, json={"url": bad_url})
    assert resp.status_code == 422
    celery_stub.ingest_delay.assert_not_called()


def test_create_project_rejects_extra_fields(auth_client):
    resp = auth_client.post(PROJECTS, json={"url": GOOD_URL, "evil": "x"})
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# List / get / delete are per-user                                            #
# --------------------------------------------------------------------------- #
def test_list_projects_is_scoped_to_owner(auth_client, other_auth_client, db, user, other_user):
    mine = make_project(db, user.id, title="Mine")
    make_project(db, other_user.id, title="Theirs")

    resp = auth_client.get(PROJECTS)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [it["id"] for it in items] == [mine.id]

    other = other_auth_client.get(PROJECTS).json()["items"]
    assert mine.id not in [it["id"] for it in other]


def test_get_foreign_project_is_404(auth_client, other_auth_client, db, user):
    project = make_project(db, user.id)
    assert other_auth_client.get(f"{PROJECTS}/{project.id}").status_code == 404
    assert other_auth_client.get(f"{PROJECTS}/{project.id}/status").status_code == 404


def test_delete_foreign_project_is_404(other_auth_client, db, user):
    project = make_project(db, user.id)
    assert other_auth_client.delete(f"{PROJECTS}/{project.id}").status_code == 404


def test_delete_own_project(auth_client, db, user):
    project = make_project(db, user.id)
    project_id = project.id
    assert auth_client.delete(f"{PROJECTS}/{project.id}").status_code == 204
    db.expunge_all()
    assert db.get(Project, project_id) is None


def test_get_project_detail_summarises_transcript(auth_client, db, user):
    project = make_project(
        db,
        user.id,
        transcript=[{"start": 0.0, "end": 1.0, "text": "hi"}, {"start": 1.0, "end": 2.0, "text": "yo"}],
    )
    body = auth_client.get(f"{PROJECTS}/{project.id}").json()
    assert body["transcript_segment_count"] == 2
    assert "transcript" not in body


# --------------------------------------------------------------------------- #
# Retry                                                                       #
# --------------------------------------------------------------------------- #
def test_retry_only_when_failed(auth_client, celery_stub, db, user):
    project = make_project(db, user.id, status="pending")
    conflict = auth_client.post(f"{PROJECTS}/{project.id}/retry")
    assert conflict.status_code == 409
    celery_stub.ingest_delay.assert_not_called()


def test_retry_failed_project_requeues(auth_client, celery_stub, db, user):
    project = make_project(db, user.id, status="failed", error_message="boom")
    resp = auth_client.post(f"{PROJECTS}/{project.id}/retry")
    assert resp.status_code == 202
    assert resp.json()["status"] == "pending"
    celery_stub.ingest_delay.assert_called_once_with(project.id)

    db.expire_all()
    refreshed = db.get(Project, project.id)
    assert refreshed.status == "pending"
    assert refreshed.error_message is None
