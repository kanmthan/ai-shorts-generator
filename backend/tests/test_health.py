"""Health probe + OpenAPI schema generation."""

from __future__ import annotations

from app.main import app


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_schema_generates():
    schema = app.openapi()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"]
    # A representative sample of routes must be documented.
    paths = schema["paths"]
    assert "/health" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/projects" in paths
    assert "/api/v1/shorts/{short_id}/export.json" in paths


def test_openapi_cached_call_is_stable():
    assert app.openapi() is app.openapi()
