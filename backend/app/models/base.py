"""Shared declarative base and reusable model mixins."""

from __future__ import annotations

from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func

from app.database import Base

__all__ = ["Base", "CreatedAtMixin", "TimestampMixin"]


class CreatedAtMixin:
    """Adds an immutable ``created_at`` column."""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class TimestampMixin(CreatedAtMixin):
    """Adds ``created_at`` and an auto-updating ``updated_at`` column."""

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
