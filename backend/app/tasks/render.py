"""Celery task: render one :class:`~app.models.render_job.RenderJob` to a 9:16 MP4.

Pipeline (``stage`` / ``progress`` in parentheses)::

    (downloading 10) download_source_segment
    (trimming    25) crop_vertical -> remove_silence
    (broll       45) overlay_broll        <- a missing asset never fails the render
    (captions    65) burn_captions
    (encoding    85) encode_final
    (uploading   95) storage.store_output
    (completed  100) persist output metadata

The task owns a short-lived :class:`~app.database.SessionLocal` session and always
removes its working directory in ``finally``.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.database import SessionLocal
from app.exceptions import ExternalServiceError
from app.logging_config import get_logger
from app.models import BrollSegment, Project, RenderJob, Short, SubtitleSegment
from app.services import rendering, storage
from app.tasks.celery_app import celery_app

logger = get_logger("tasks.render")

_ERROR_MAX_LEN = 2000
_ACTIVE_STATUSES = ("queued", "processing")


class _RenderCancelled(Exception):
    """Raised internally when a job is cancelled mid-flight."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _set_stage(db: Any, job: RenderJob, stage: str, progress: int) -> None:
    job.stage = stage
    job.progress = progress
    db.commit()
    logger.info("RenderJob %s -> stage=%s progress=%s", job.id, stage, progress)


def _guard_not_cancelled(db: Any, job_id: int) -> None:
    current = (
        db.query(RenderJob.status).filter(RenderJob.id == job_id).first()
    )
    if current is not None and current[0] == "cancelled":
        raise _RenderCancelled


@celery_app.task(name="app.tasks.render.render_short")
def render_short(render_job_id: int) -> dict[str, Any]:
    """Execute the full staged render pipeline for ``render_job_id``."""
    db = SessionLocal()
    workdir = Path(tempfile.mkdtemp(prefix=f"render_{render_job_id}_"))
    try:
        job = db.query(RenderJob).filter(RenderJob.id == render_job_id).first()
        if job is None:
            logger.error("render_short: RenderJob %s not found", render_job_id)
            return {"render_job_id": render_job_id, "status": "missing"}
        if job.status == "cancelled":
            logger.info("render_short: RenderJob %s already cancelled", render_job_id)
            return {"render_job_id": render_job_id, "status": "cancelled"}

        short = db.query(Short).filter(Short.id == job.short_id).first()
        if short is None:
            raise ExternalServiceError(f"Short {job.short_id} no longer exists")
        project = db.query(Project).filter(Project.id == short.project_id).first()
        if project is None or not project.url:
            raise ExternalServiceError("Source project/URL is unavailable")

        broll_segments = (
            db.query(BrollSegment)
            .filter(BrollSegment.short_id == short.id)
            .order_by(BrollSegment.id)
            .all()
        )
        subtitle_segments = (
            db.query(SubtitleSegment)
            .filter(SubtitleSegment.short_id == short.id)
            .order_by(SubtitleSegment.id)
            .all()
        )

        try:
            job.status = "processing"
            job.started_at = _utcnow()
            job.error_message = None
            short.status = "rendering"
            _set_stage(db, job, "downloading", 10)

            segment = rendering.download_source_segment(
                project.url, short.start_time, short.end_time, workdir
            )

            _guard_not_cancelled(db, job.id)
            _set_stage(db, job, "trimming", 25)
            vertical = rendering.crop_vertical(segment, workdir)
            desilenced = rendering.remove_silence(vertical, workdir)

            _guard_not_cancelled(db, job.id)
            _set_stage(db, job, "broll", 45)
            try:
                with_broll = rendering.overlay_broll(desilenced, broll_segments, workdir)
            except ExternalServiceError as exc:  # a bad/missing asset must not fail us
                logger.warning(
                    "render_short: B-roll overlay failed for job %s, continuing: %s",
                    job.id,
                    exc,
                )
                with_broll = desilenced

            _guard_not_cancelled(db, job.id)
            _set_stage(db, job, "captions", 65)
            captioned = rendering.burn_captions(with_broll, subtitle_segments, workdir)

            _guard_not_cancelled(db, job.id)
            _set_stage(db, job, "encoding", 85)
            final_path = rendering.encode_final(captioned, workdir)

            _guard_not_cancelled(db, job.id)
            _set_stage(db, job, "uploading", 95)
            key = f"renders/{job.user_id}/{job.id}.mp4"
            output_url = storage.store_output(final_path, key)

            job.output_url = output_url
            job.file_size_bytes = final_path.stat().st_size
            job.output_format = "mp4"
            job.video_codec = "h264"
            job.audio_codec = "aac"
            job.resolution = "1080x1920"
            job.aspect_ratio = "9:16"
            job.stage = None
            job.progress = 100
            job.status = "completed"
            job.completed_at = _utcnow()
            short.status = "rendered"
            db.commit()
            logger.info("render_short: RenderJob %s completed -> %s", job.id, output_url)
            return {"render_job_id": job.id, "status": "completed"}

        except _RenderCancelled:
            db.rollback()
            _finalise_cancelled(db, render_job_id)
            return {"render_job_id": render_job_id, "status": "cancelled"}
        except Exception as exc:
            db.rollback()
            _finalise_failed(db, render_job_id, exc)
            return {
                "render_job_id": render_job_id,
                "status": "failed",
                "error": str(exc),
            }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        db.close()


def _finalise_cancelled(db: Any, render_job_id: int) -> None:
    try:
        job = db.query(RenderJob).filter(RenderJob.id == render_job_id).first()
        if job is not None:
            job.status = "cancelled"
            job.stage = None
            job.completed_at = _utcnow()
            if job.short is not None and job.short.status == "rendering":
                job.short.status = "draft"
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist cancelled state for RenderJob %s", render_job_id)


def _finalise_failed(db: Any, render_job_id: int, exc: Exception) -> None:
    message = (str(exc) or exc.__class__.__name__)[:_ERROR_MAX_LEN]
    logger.exception("render_short failed for RenderJob %s: %s", render_job_id, message)
    try:
        job = db.query(RenderJob).filter(RenderJob.id == render_job_id).first()
        if job is not None:
            job.status = "failed"
            job.error_message = message
            job.completed_at = _utcnow()
            if job.short is not None:
                job.short.status = "failed"
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist failed state for RenderJob %s", render_job_id)
