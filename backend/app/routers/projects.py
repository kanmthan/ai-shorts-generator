"""Projects & Video Ingestion API routes.

All endpoints require a valid Bearer access token and operate **only** on rows
owned by the caller - a project belonging to another user is indistinguishable
from one that does not exist (``404``).

The ``POST`` handler does the minimum synchronous work: SSRF-validate the URL,
create a ``pending`` :class:`~app.models.Project`, and enqueue the Celery
``ingest_project`` task. No yt-dlp / network / transcript work ever runs in the
request path.

Rate limiting
-------------
``limiter`` below is a module-level ``slowapi`` limiter keyed by remote address.
For it to take effect ``app/main.py`` must wire it into the app once, e.g.::

    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from app.routers import projects

    app.state.limiter = projects.limiter          # or a shared app-wide Limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

If ``app.state.limiter`` is already set by ``main.py`` this module reuses that
instance instead of creating a second one.
"""


from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.exceptions import ConflictError, NotFoundError
from app.logging_config import get_logger
from app.models import Project, User
from app.rate_limit import limiter
from app.schemas.project import (
    Paginated,
    ProjectCreate,
    ProjectListItem,
    ProjectOut,
    ProjectStatusOut,
)
from app.services.url_guard import validate_public_url
from app.tasks.ingest import ingest_project

logger = get_logger("routers.projects")

# Module-level limiter (keyed by client IP). main.py attaches it to the app -
# see the module docstring. Reused if main.py already created one.

# Retriable / active lifecycle states.
_FAILED_STATUS = "failed"
_PENDING_STATUS = "pending"

# Explicit column tuples - never "SELECT *".
_LIST_COLUMNS = (
    Project.id,
    Project.url,
    Project.title,
    Project.platform,
    Project.status,
    Project.duration_seconds,
    Project.thumbnail_url,
    Project.created_at,
)
_STATUS_COLUMNS = (Project.id, Project.status, Project.error_message)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _get_owned_project(db: Session, project_id: int, user_id: int) -> Project:
    """Load a project by id scoped to ``user_id`` or raise ``NotFoundError``."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user_id)
        .first()
    )
    if project is None:
        raise NotFoundError("Project")
    return project


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ProjectOut)
@limiter.limit("10/minute")
async def create_project(
    request: Request,
    payload: ProjectCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectOut:
    """Validate + persist a new project and enqueue ingestion (202)."""
    safe_url = validate_public_url(str(payload.url))
    project = Project(url=safe_url, user_id=current_user.id, status=_PENDING_STATUS)
    db.add(project)
    db.commit()
    db.refresh(project)

    ingest_project.delay(project.id)
    logger.info("Project %s created by user %s; ingestion enqueued", project.id, current_user.id)
    return ProjectOut.from_model(project)


@router.get("", response_model=Paginated[ProjectListItem])
async def list_projects(
    db: DbSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Paginated[ProjectListItem]:
    """Paginated list of the caller's projects, newest first."""
    owned = Project.user_id == current_user.id
    total = int(db.query(func.count(Project.id)).filter(owned).scalar() or 0)
    rows = (
        db.query(*_LIST_COLUMNS)
        .filter(owned)
        .order_by(Project.created_at.desc(), Project.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [ProjectListItem.from_row(row) for row in rows]
    return Paginated.build(items, total=total, page=page, page_size=size)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectOut:
    """Full project detail (transcript summarised, never inlined)."""
    project = _get_owned_project(db, project_id, current_user.id)
    return ProjectOut.from_model(project)


@router.get("/{project_id}/status", response_model=ProjectStatusOut)
async def get_project_status(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectStatusOut:
    """Lightweight status poll."""
    row = (
        db.query(*_STATUS_COLUMNS)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if row is None:
        raise NotFoundError("Project")
    return ProjectStatusOut.from_row(row)


@router.post(
    "/{project_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ProjectOut,
)
async def retry_project(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectOut:
    """Re-run ingestion for a project that previously failed."""
    project = _get_owned_project(db, project_id, current_user.id)
    if project.status != _FAILED_STATUS:
        raise ConflictError("Only a failed project can be retried")

    project.status = _PENDING_STATUS
    project.error_message = None
    db.commit()
    db.refresh(project)

    ingest_project.delay(project.id)
    logger.info("Project %s re-queued for ingestion by user %s", project.id, current_user.id)
    return ProjectOut.from_model(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    """Delete a project and (via cascade) its derived shorts / renders."""
    project = _get_owned_project(db, project_id, current_user.id)
    db.delete(project)
    db.commit()
    logger.info("Project %s deleted by user %s", project_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
