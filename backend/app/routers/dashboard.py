"""Dashboard & Settings API routes.

Endpoints (all require a valid Bearer access token):

* ``GET /api/v1/dashboard/stats`` -> :class:`~app.schemas.dashboard.DashboardStats`
* ``GET /api/v1/usage`` -> :class:`~app.schemas.dashboard.UsageStats`
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.logging_config import get_logger
from app.models import User
from app.schemas.dashboard import DashboardStats, UsageStats
from app.services import dashboard_service

logger = get_logger("dashboard_router")

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DashboardStats:
    """Aggregate counters (projects, shorts, renders, storage) for the user."""
    return dashboard_service.get_stats(db, current_user.id)


@router.get("/usage", response_model=UsageStats)
async def get_usage_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UsageStats:
    """Metered Claude token / stock-API usage for the current calendar month."""
    return dashboard_service.get_usage(db, current_user.id)
