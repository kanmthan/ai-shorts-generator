"""Celery tasks for the Shorts Analysis module.

* ``app.tasks.analyze.analyze_project`` - run Claude analysis for a project,
  persist its shorts, best-effort fetch stock B-roll for every segment, and move
  the project to ``ready`` / ``failed``.
* ``app.tasks.analyze.refetch_short_broll`` - re-run the stock B-roll search for a
  single short's segments (used by ``POST /shorts/{id}/broll/refetch``).

Each task opens its own ``SessionLocal`` and always closes it in ``finally``.
"""

from __future__ import annotations

from typing import Any

from app.database import SessionLocal
from app.logging_config import get_logger
from app.models import BrollSegment, Project, Short
from app.services.analysis import run_analysis
from app.services.broll import fetch_broll_asset
from app.tasks.celery_app import celery_app

logger = get_logger("tasks.analyze")

__all__ = ["analyze_project", "refetch_short_broll"]


@celery_app.task(name="app.tasks.analyze.analyze_project", bind=True)
def analyze_project(self: Any, project_id: int) -> dict[str, Any]:
    """Analyse ``project_id`` end to end and set its final status.

    Returns ``{"created": int, "partial": bool}`` from :func:`run_analysis`.
    On any failure the project is marked ``failed`` with ``error_message`` and
    the exception is re-raised so Celery records the failure.
    """
    db = SessionLocal()
    try:
        result = run_analysis(db, project_id)

        segments = (
            db.query(BrollSegment)
            .join(Short, BrollSegment.short_id == Short.id)
            .filter(Short.project_id == project_id)
            .all()
        )
        _apply_broll_assets(segments)
        db.commit()

        project = db.query(Project).filter(Project.id == project_id).first()
        if project is not None:
            project.status = "ready"
            project.error_message = None
            db.commit()

        logger.info("analyze_project done: project=%s result=%s", project_id, result)
        return result
    except Exception as exc:  # mark project failed, then re-raise
        db.rollback()
        logger.exception("analyze_project failed for project %s", project_id)
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is not None:
            project.status = "failed"
            project.error_message = str(exc)[:1000]
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.analyze.refetch_short_broll", bind=True)
def refetch_short_broll(self: Any, short_id: int) -> dict[str, Any]:
    """Re-run the stock B-roll search for one short's segments."""
    db = SessionLocal()
    try:
        segments = (
            db.query(BrollSegment).filter(BrollSegment.short_id == short_id).all()
        )
        updated = _apply_broll_assets(segments)
        db.commit()
        logger.info("refetch_short_broll: short=%s updated=%d", short_id, updated)
        return {"short_id": short_id, "updated": updated}
    except Exception:
        db.rollback()
        logger.exception("refetch_short_broll failed for short %s", short_id)
        raise
    finally:
        db.close()


def _apply_broll_assets(segments: list[BrollSegment]) -> int:
    """Best-effort: resolve and write a stock asset onto each B-roll segment."""
    updated = 0
    for seg in segments:
        try:
            asset = fetch_broll_asset(
                {
                    "search_keywords": seg.search_keywords or [],
                    "use_broll": seg.use_broll,
                }
            )
        except Exception:  # never let one segment kill the task
            logger.warning("B-roll fetch raised for segment %s; skipping", seg.id)
            continue
        seg.asset_url = asset["asset_url"]
        seg.asset_source = asset["asset_source"]
        seg.asset_status = asset["asset_status"]
        updated += 1
    return updated
