"""Shorts Analysis API routes.

All endpoints require a Bearer access token and authorise through the parent
``Project.user_id`` - a user can only ever see or mutate shorts derived from
their own projects.

| Method | Path                                          | Result |
|--------|-----------------------------------------------|--------|
| GET    | /api/v1/projects/{project_id}/shorts          | list[ShortCardOut] |
| GET    | /api/v1/shorts/{short_id}                     | ShortOut |
| GET    | /api/v1/shorts/{short_id}/export.json         | ShortsExportEnvelope |
| POST   | /api/v1/projects/{project_id}/shorts/regenerate | 202 |
| PATCH  | /api/v1/shorts/{short_id}                     | ShortOut |
| POST   | /api/v1/shorts/{short_id}/broll/refetch       | 202 |
| DELETE | /api/v1/shorts/{short_id}                     | 204 |
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.dependencies import get_current_user, get_db
from app.exceptions import NotFoundError
from app.logging_config import get_logger
from app.models import BrollSegment, Project, Short, User
from app.rate_limit import limiter
from app.schemas.export import (
    BrollExport,
    EditingOut,
    ScoresOut,
    ShortExport,
    ShortsExportEnvelope,
    SourceVideoOut,
    SubtitleExport,
)
from app.schemas.short import ShortCardOut, ShortOut, ShortUpdate
from app.tasks.celery_app import celery_app

logger = get_logger("routers.shorts")

router = APIRouter(prefix="/api/v1", tags=["shorts"])

_ANALYZE_TASK = "app.tasks.analyze.analyze_project"
_REFETCH_TASK = "app.tasks.analyze.refetch_short_broll"

_SCORE_KEYS = (
    "hook_strength",
    "standalone_value",
    "engagement",
    "retention",
    "payoff",
    "clarity",
    "shareability",
    "viral_potential",
    "b_roll_quality",
)


# --------------------------------------------------------------------------- #
# Authz helpers                                                               #
# --------------------------------------------------------------------------- #
def _owned_project(db: Session, project_id: int, user: User) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .first()
    )
    if project is None:
        raise NotFoundError("Project")
    return project


def _owned_short(db: Session, short_id: int, user: User, *, with_segments: bool) -> Short:
    query = (
        db.query(Short)
        .join(Project, Short.project_id == Project.id)
        .filter(Short.id == short_id, Project.user_id == user.id)
    )
    if with_segments:
        query = query.options(
            selectinload(Short.broll_segments),
            selectinload(Short.subtitle_segments),
        )
    short = query.first()
    if short is None:
        raise NotFoundError("Short")
    return short


# --------------------------------------------------------------------------- #
# Read                                                                        #
# --------------------------------------------------------------------------- #
@router.get("/projects/{project_id}/shorts", response_model=list[ShortCardOut])
async def list_shorts(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ShortCardOut]:
    """Return the ShortCard preview payload for every short in a project."""
    _owned_project(db, project_id, current_user)
    shorts = (
        db.query(Short)
        .filter(Short.project_id == project_id)
        .options(selectinload(Short.broll_segments))
        .order_by(Short.index.asc())
        .all()
    )
    return [ShortCardOut.from_model(short) for short in shorts]


@router.get("/shorts/{short_id}", response_model=ShortOut)
async def get_short(
    short_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ShortOut:
    """Return one short in full: scores, editing, B-roll and subtitle segments."""
    short = _owned_short(db, short_id, current_user, with_segments=True)
    return ShortOut.model_validate(short)


@router.get("/shorts/{short_id}/export.json", response_model=ShortsExportEnvelope)
async def export_short(
    short_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ShortsExportEnvelope:
    """Return the short as a single-item envelope in the master JSON format."""
    short = _owned_short(db, short_id, current_user, with_segments=True)
    project = db.query(Project).filter(Project.id == short.project_id).first()

    sibling_count = (
        db.query(func.count(Short.id))
        .filter(Short.project_id == short.project_id)
        .scalar()
    ) or 0

    return ShortsExportEnvelope(
        status="partial" if sibling_count < 5 else "success",
        source_video=SourceVideoOut(
            url=getattr(project, "url", "") or "",
            title=getattr(project, "title", None),
            duration_seconds=getattr(project, "duration_seconds", None) or 0,
        ),
        total_shorts=1,
        shorts=[_short_to_export(short)],
    )


# --------------------------------------------------------------------------- #
# Mutate                                                                      #
# --------------------------------------------------------------------------- #
@router.post(
    "/projects/{project_id}/shorts/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("5/hour")
async def regenerate_shorts(
    request: Request,
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """Re-enqueue Claude analysis for the project (existing shorts are replaced)."""
    project = _owned_project(db, project_id, current_user)
    project.status = "analyzing"
    project.error_message = None
    db.commit()

    async_result = celery_app.send_task(_ANALYZE_TASK, args=[project_id])
    logger.info(
        "Re-enqueued analysis for project %s (task=%s id=%s)",
        project_id,
        _ANALYZE_TASK,
        async_result.id,
    )
    return {
        "project_id": project_id,
        "status": "analyzing",
        "task_id": async_result.id,
    }


@router.patch("/shorts/{short_id}", response_model=ShortOut)
async def update_short(
    short_id: int,
    payload: ShortUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ShortOut:
    """Manually tweak a short's trim range, title, caption or hashtags."""
    short = _owned_short(db, short_id, current_user, with_segments=True)
    data = payload.model_dump(exclude_unset=True)

    if "title" in data:
        short.title = data["title"]
    if "caption" in data:
        short.caption = data["caption"]
    if "hashtags" in data:
        short.hashtags = list(data["hashtags"] or [])
    if data.get("start_time"):
        short.start_time = data["start_time"]
    if data.get("end_time"):
        short.end_time = data["end_time"]

    if data.get("start_time") or data.get("end_time"):
        start_s = _ts_to_seconds(short.start_time)
        end_s = _ts_to_seconds(short.end_time)
        if start_s is not None and end_s is not None and end_s > start_s:
            short.duration_seconds = round(end_s - start_s, 2)

    db.commit()
    db.refresh(short)
    return ShortOut.model_validate(short)


@router.post(
    "/shorts/{short_id}/broll/refetch",
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
async def refetch_broll(
    request: Request,
    short_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """Re-enqueue the stock B-roll search for this short's segments."""
    short = _owned_short(db, short_id, current_user, with_segments=False)
    db.query(BrollSegment).filter(
        BrollSegment.short_id == short.id,
        BrollSegment.use_broll.is_(True),
    ).update({BrollSegment.asset_status: "pending"}, synchronize_session=False)
    db.commit()

    async_result = celery_app.send_task(_REFETCH_TASK, args=[short.id])
    logger.info("Re-enqueued B-roll refetch for short %s (id=%s)", short.id, async_result.id)
    return {"short_id": short.id, "task_id": async_result.id}


@router.delete(
    "/shorts/{short_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_short(
    short_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Delete a short (cascades to its B-roll and subtitle segments)."""
    short = _owned_short(db, short_id, current_user, with_segments=False)
    db.delete(short)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Master-format serialisation                                                 #
# --------------------------------------------------------------------------- #
def _short_to_export(short: Short) -> ShortExport:
    """Serialise a persisted ``Short`` row to the master export shape."""
    broll = [_broll_to_export(seg) for seg in short.broll_segments]
    if not broll:
        broll = [
            BrollExport(
                start="00:00",
                end="00:00",
                use_broll=False,
                reason="No B-roll segments were planned for this short.",
                search_keywords=[],
            )
        ]
    return ShortExport(
        id=f"short_{short.index}",
        start_time=short.start_time,
        end_time=short.end_time,
        duration_seconds=int(round(short.duration_seconds or 0)),
        title=short.title or "",
        hook=short.hook,
        summary=short.summary,
        reason=short.reason,
        scores=_scores_to_export(short.scores),
        caption=short.caption,
        hashtags=list(short.hashtags or []),
        editing=EditingOut.model_validate(short.editing or {}),
        broll_segments=broll,
        subtitle_segments=[
            SubtitleExport(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                highlight_words=list(seg.highlight_words) if seg.highlight_words else None,
            )
            for seg in short.subtitle_segments
        ],
    )


def _broll_to_export(seg: BrollSegment) -> BrollExport:
    return BrollExport(
        start=seg.start,
        end=seg.end,
        original_start=seg.original_start,
        original_end=seg.original_end,
        duration_seconds=seg.duration_seconds,
        description=seg.description,
        reason=seg.reason,
        search_keywords=list(seg.search_keywords or []),
        type=seg.type,
        transition=seg.transition,
        placement=seg.placement,
        use_broll=bool(seg.use_broll),
    )


def _scores_to_export(raw: dict | None) -> ScoresOut:
    """Coerce a stored scores dict into a valid :class:`ScoresOut` (clamped 1-10)."""
    data = raw or {}
    merged: dict[str, float] = {}
    for key in _SCORE_KEYS:
        merged[key] = _clamp(data.get(key, 1.0), 1.0, 10.0)
    merged["overall"] = _clamp(data.get("overall", 0.0), 0.0, 10.0)
    return ScoresOut.model_validate(merged)


def _clamp(value: object, lo: float, hi: float) -> float:
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        num = lo
    return max(lo, min(hi, num))


def _ts_to_seconds(value: str | None) -> float | None:
    """Parse ``HH:MM:SS`` / ``MM:SS`` / ``SS`` to seconds."""
    if not value or not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if not 1 <= len(parts) <= 3:
        return None
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    seconds = 0.0
    for num in nums:
        seconds = seconds * 60.0 + num
    return seconds
