"""Rendering & Export API routes.

All endpoints require a valid Bearer access token and enforce per-user
ownership (a render job is reachable only by the user who created it; a short is
renderable only by the user who owns its parent project).

``ffmpeg`` / ``yt-dlp`` never run in a request handler - ``POST .../render`` only
creates a :class:`~app.models.render_job.RenderJob` row and enqueues
:func:`app.tasks.render.render_short`.
"""


from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.exceptions import ConflictError, NotFoundError
from app.logging_config import get_logger
from app.models import Project, RenderJob, Short, User
from app.rate_limit import limiter
from app.schemas.render import RenderEnqueueResponse, RenderJobListItem, RenderJobOut
from app.services import storage
from app.tasks.render import render_short

logger = get_logger("render_jobs_router")

router = APIRouter(prefix="/api/v1", tags=["render"])

_ACTIVE_STATUSES = ("queued", "processing")
_CANCELLABLE_STATUSES = ("queued", "processing")

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _owned_job(db: Session, job_id: int, user_id: int) -> RenderJob:
    """Return the caller's render job or raise 404 (also hides other users' jobs)."""
    job = (
        db.query(RenderJob)
        .filter(RenderJob.id == job_id, RenderJob.user_id == user_id)
        .first()
    )
    if job is None:
        raise NotFoundError("Render job not found")
    return job


def _owned_short(db: Session, short_id: int, user_id: int) -> Short:
    """Return a short owned (via its project) by the caller, or raise 404."""
    short = (
        db.query(Short)
        .join(Project, Short.project_id == Project.id)
        .filter(Short.id == short_id, Project.user_id == user_id)
        .first()
    )
    if short is None:
        raise NotFoundError("Short not found")
    return short


@router.post(
    "/shorts/{short_id}/render",
    response_model=RenderEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
async def enqueue_render(
    request: Request,
    short_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> RenderEnqueueResponse:
    """Queue a render for a short. 409 if one is already queued/processing."""
    short = _owned_short(db, short_id, current_user.id)

    active = (
        db.query(RenderJob.id)
        .filter(
            RenderJob.short_id == short.id,
            RenderJob.status.in_(_ACTIVE_STATUSES),
        )
        .first()
    )
    if active is not None:
        raise ConflictError("A render job for this short is already in progress")

    job = RenderJob(status="queued", short_id=short.id, user_id=current_user.id)
    db.add(job)
    short.status = "queued"
    db.commit()
    db.refresh(job)

    render_short.delay(job.id)
    logger.info("Enqueued RenderJob %s for short %s (user %s)", job.id, short.id, current_user.id)
    return RenderEnqueueResponse(job_id=job.id, status=job.status)


@router.get("/render-jobs/{job_id}", response_model=RenderJobOut)
async def get_render_job(
    job_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> RenderJob:
    """Status + progress + stage for one render job (UI polls this)."""
    return _owned_job(db, job_id, current_user.id)


@router.get("/render-jobs", response_model=list[RenderJobListItem])
async def list_render_jobs(
    db: DbSession,
    current_user: CurrentUser,
) -> list[RenderJobListItem]:
    """List the caller's render jobs, newest first."""
    rows = (
        db.query(
            RenderJob.id,
            RenderJob.short_id,
            RenderJob.status,
            RenderJob.progress,
            RenderJob.stage,
            RenderJob.output_url,
            RenderJob.file_size_bytes,
            RenderJob.error_message,
            RenderJob.created_at,
            RenderJob.completed_at,
        )
        .filter(RenderJob.user_id == current_user.id)
        .order_by(RenderJob.created_at.desc(), RenderJob.id.desc())
        .all()
    )
    return [RenderJobListItem.model_validate(row) for row in rows]


@router.get("/render-jobs/{job_id}/download", response_model=None)
async def download_render_job(
    job_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse | RedirectResponse:
    """Stream the finished local MP4, or redirect to its storage URL. 404 until done."""
    job = _owned_job(db, job_id, current_user.id)
    if job.status != "completed" or not job.output_url:
        raise NotFoundError("Render output is not ready")

    filename = f"short-{job.short_id}-render-{job.id}.mp4"
    if job.output_url.startswith("/media/"):
        path = storage.local_media_path(job.output_url[len("/media/") :])
        if not path.is_file():
            raise NotFoundError("Render output file is missing")
        return FileResponse(path, media_type="video/mp4", filename=filename)

    return RedirectResponse(url=job.output_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post("/render-jobs/{job_id}/cancel", response_model=RenderJobOut)
async def cancel_render_job(
    job_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> RenderJob:
    """Cancel a queued/processing job. 409 if it already finished."""
    job = _owned_job(db, job_id, current_user.id)
    if job.status not in _CANCELLABLE_STATUSES:
        raise ConflictError(f"Render job is {job.status} and cannot be cancelled")

    job.status = "cancelled"
    job.stage = None
    if job.short is not None and job.short.status in ("queued", "rendering"):
        job.short.status = "draft"
    db.commit()
    db.refresh(job)
    logger.info("Cancelled RenderJob %s (user %s)", job.id, current_user.id)
    return job
