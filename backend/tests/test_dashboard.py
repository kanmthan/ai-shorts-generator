"""Dashboard & Settings: /dashboard/stats and /usage."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.conftest import make_project, make_render_job, make_short


def _seed(db, user_id, *, projects_ready, projects_pending, shorts, completed_renders, queued_renders):
    first_short = None
    for _ in range(projects_ready):
        p = make_project(db, user_id, status="ready")
        for i in range(shorts if first_short is None else 0):
            s = make_short(db, p.id, index=i + 1)
            first_short = first_short or s
    for _ in range(projects_pending):
        make_project(db, user_id, status="pending")
    for _ in range(completed_renders):
        make_render_job(
            db, first_short.id, user_id, status="completed", file_size_bytes=1_000, progress=100
        )
    for _ in range(queued_renders):
        make_render_job(db, first_short.id, user_id, status="queued")


def test_dashboard_stats_counts_current_user_only(auth_client, db, user, other_user):
    _seed(
        db,
        user.id,
        projects_ready=2,
        projects_pending=1,
        shorts=3,
        completed_renders=2,
        queued_renders=1,
    )
    _seed(
        db,
        other_user.id,
        projects_ready=5,
        projects_pending=4,
        shorts=7,
        completed_renders=6,
        queued_renders=3,
    )

    body = auth_client.get("/api/v1/dashboard/stats").json()
    assert body["projects_total"] == 3
    assert body["projects_ready"] == 2
    assert body["shorts_total"] == 3
    assert body["renders_total"] == 3
    assert body["renders_completed"] == 2
    assert body["storage_bytes"] == 2_000


def test_dashboard_stats_zero_for_new_user(auth_client):
    body = auth_client.get("/api/v1/dashboard/stats").json()
    assert body == {
        "projects_total": 0,
        "projects_ready": 0,
        "shorts_total": 0,
        "renders_total": 0,
        "renders_completed": 0,
        "storage_bytes": 0,
    }


def test_dashboard_requires_auth(client):
    assert client.get("/api/v1/dashboard/stats").status_code == 401


def test_usage_returns_current_month_window_zeroed(auth_client):
    body = auth_client.get("/api/v1/usage").json()
    start = datetime.fromisoformat(body["period_start"])
    end = datetime.fromisoformat(body["period_end"])
    now = datetime.now(UTC)

    assert start.day == 1
    assert start <= now < end
    assert end > start
    assert body["claude_input_tokens"] == 0
    assert body["claude_output_tokens"] == 0
    assert body["stock_api_calls"] == 0


def test_usage_requires_auth(client):
    assert client.get("/api/v1/usage").status_code == 401
