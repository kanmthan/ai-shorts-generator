"""Business logic for the Dashboard & Settings module.

All queries are ``func.count`` / ``func.sum`` aggregates scoped to a single
user - no ``SELECT *`` and no per-row (N+1) access.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import Project, RenderJob, Short
from app.schemas.dashboard import DashboardStats, UsageStats

logger = get_logger("dashboard_service")


def get_stats(db: Session, user_id: int) -> DashboardStats:
    """Return aggregate dashboard counters for ``user_id``.

    Args:
        db: Active SQLAlchemy session.
        user_id: Primary key of the authenticated user.

    Returns:
        A populated :class:`DashboardStats`.
    """
    # Projects: total + how many reached the "ready" state.
    project_row = db.execute(
        select(
            func.count(Project.id),
            func.count(Project.id).filter(Project.status == "ready"),
        ).where(Project.user_id == user_id)
    ).one()
    projects_total, projects_ready = int(project_row[0]), int(project_row[1])

    # Shorts: count across all projects owned by the user (single JOIN, aggregate).
    shorts_total = int(
        db.execute(
            select(func.count(Short.id))
            .select_from(Short)
            .join(Project, Short.project_id == Project.id)
            .where(Project.user_id == user_id)
        ).scalar_one()
    )

    # Render jobs: total, completed, and bytes of output for completed jobs.
    render_row = db.execute(
        select(
            func.count(RenderJob.id),
            func.count(RenderJob.id).filter(RenderJob.status == "completed"),
            func.coalesce(
                func.sum(RenderJob.file_size_bytes).filter(
                    RenderJob.status == "completed"
                ),
                0,
            ),
        ).where(RenderJob.user_id == user_id)
    ).one()
    renders_total, renders_completed = int(render_row[0]), int(render_row[1])
    storage_bytes = int(render_row[2] or 0)

    logger.debug(
        "dashboard stats user_id=%s projects=%s/%s shorts=%s renders=%s/%s bytes=%s",
        user_id,
        projects_ready,
        projects_total,
        shorts_total,
        renders_completed,
        renders_total,
        storage_bytes,
    )

    return DashboardStats(
        projects_total=projects_total,
        projects_ready=projects_ready,
        shorts_total=shorts_total,
        renders_total=renders_total,
        renders_completed=renders_completed,
        storage_bytes=storage_bytes,
    )


def _current_month_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return ``(period_start, period_end)`` for the current UTC calendar month."""
    ref = now or datetime.now(UTC)
    period_start = ref.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    if period_start.month == 12:
        period_end = period_start.replace(year=period_start.year + 1, month=1)
    else:
        period_end = period_start.replace(month=period_start.month + 1)
    return period_start, period_end


def get_usage(db: Session, user_id: int) -> UsageStats:
    """Return metered usage for ``user_id`` for the current calendar month.

    Args:
        db: Active SQLAlchemy session (unused until a metering table exists).
        user_id: Primary key of the authenticated user.

    Returns:
        A :class:`UsageStats` with the correct period window. Token / stock-API
        counters are ``0`` until metering is wired up.
    """
    period_start, period_end = _current_month_bounds()

    # TODO wire metering: there is no usage/metering table yet (see PRP Module 5).
    # Once request-level accounting exists, replace the zeros below with
    # aggregate func.sum() queries filtered by user_id and the period window.
    _ = (db, user_id)

    return UsageStats(
        period_start=period_start,
        period_end=period_end,
        claude_input_tokens=0,
        claude_output_tokens=0,
        stock_api_calls=0,
    )
