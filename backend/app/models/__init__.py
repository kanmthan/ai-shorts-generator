"""SQLAlchemy models package.

Every model class is imported and re-exported here so that:

* ``from app.models import User`` works everywhere, and
* Alembic autogenerate sees the full metadata by importing this one module.
"""

from __future__ import annotations

from app.models.base import Base, CreatedAtMixin, TimestampMixin
from app.models.project import PROJECT_STATUSES, Project
from app.models.refresh_token import RefreshToken
from app.models.render_job import (
    RENDER_JOB_STAGES,
    RENDER_JOB_STATUSES,
    RenderJob,
)
from app.models.short import (
    BROLL_ASSET_SOURCES,
    BROLL_ASSET_STATUSES,
    BROLL_PLACEMENTS,
    BROLL_TRANSITIONS,
    BROLL_TYPES,
    SHORT_STATUSES,
    BrollSegment,
    Short,
    SubtitleSegment,
)
from app.models.user import OAUTH_PROVIDERS, User

__all__ = [
    "Base",
    "CreatedAtMixin",
    "TimestampMixin",
    "User",
    "OAUTH_PROVIDERS",
    "RefreshToken",
    "Project",
    "PROJECT_STATUSES",
    "Short",
    "SHORT_STATUSES",
    "BrollSegment",
    "BROLL_TYPES",
    "BROLL_TRANSITIONS",
    "BROLL_PLACEMENTS",
    "BROLL_ASSET_SOURCES",
    "BROLL_ASSET_STATUSES",
    "SubtitleSegment",
    "RenderJob",
    "RENDER_JOB_STATUSES",
    "RENDER_JOB_STAGES",
]
