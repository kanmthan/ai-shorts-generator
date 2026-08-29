"""Celery task: ingest one submitted project.

Pipeline (status transitions in parentheses)::

    (fetching)     fetch_metadata  -> persist title / duration / platform /
                                      external_id / thumbnail
    (transcribing) fetch_transcript -> persist transcript + language
    (analyzing)    hand off to app.tasks.analyze.analyze_project

Any failure moves the project to ``failed`` with a human-readable
``error_message`` - this is always persisted before the task returns.

The task owns its own short-lived :class:`~app.database.SessionLocal` session
(the FastAPI request-scoped ``get_db`` dependency is not available here) and
closes it in ``finally``.
"""

from __future__ import annotations

from typing import Any

from app.database import SessionLocal
from app.logging_config import get_logger
from app.models import Project
from app.services.ingestion import fetch_metadata
from app.services.transcript import fetch_transcript
from app.tasks.celery_app import celery_app

logger = get_logger("tasks.ingest")

_ANALYZE_TASK = "app.tasks.analyze.analyze_project"
_ERROR_MAX_LEN = 2000


@celery_app.task(name="app.tasks.ingest.ingest_project", bind=True)
def ingest_project(self: Any, project_id: int) -> dict[str, Any]:
    """Run metadata + transcript ingestion for ``project_id`` then enqueue analysis."""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            logger.error("ingest_project: project %s not found", project_id)
            return {"project_id": project_id, "status": "missing"}

        try:
            _set_status(db, project, "fetching")
            meta = fetch_metadata(project.url)
            project.title = meta.title
            project.duration_seconds = meta.duration_seconds
            project.platform = meta.platform
            project.external_id = meta.video_id
            project.thumbnail_url = meta.thumbnail_url
            db.commit()

            _set_status(db, project, "transcribing")
            segments = fetch_transcript(project.url, meta.video_id, meta.platform)
            project.transcript = list(segments)
            project.language = getattr(segments, "language", None)
            db.commit()

            _set_status(db, project, "analyzing")
        except Exception as exc:
            _mark_failed(db, project_id, exc)
            return {"project_id": project_id, "status": "failed", "error": str(exc)}

        celery_app.send_task(_ANALYZE_TASK, args=[project_id])
        logger.info("ingest_project: project %s handed off to %s", project_id, _ANALYZE_TASK)
        return {"project_id": project_id, "status": "analyzing"}
    finally:
        db.close()


def _set_status(db: Any, project: Project, status: str) -> None:
    project.status = status
    project.error_message = None
    db.commit()
    logger.info("Project %s -> %s", project.id, status)


def _mark_failed(db: Any, project_id: int, exc: Exception) -> None:
    """Persist ``failed`` status + error message; never raises."""
    message = (str(exc) or exc.__class__.__name__)[:_ERROR_MAX_LEN]
    logger.exception("ingest_project failed for project %s: %s", project_id, message)
    try:
        db.rollback()
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is not None:
            project.status = "failed"
            project.error_message = message
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist failed state for project %s", project_id)
