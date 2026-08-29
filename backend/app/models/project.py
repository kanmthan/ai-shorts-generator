"""Project model - one submitted long-form video and its ingestion state."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin

# Allowed lifecycle states for a project.
PROJECT_STATUSES = (
    "pending",
    "fetching",
    "transcribing",
    "analyzing",
    "ready",
    "failed",
)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url = Column(String(2048), nullable=False)
    platform = Column(String(50), nullable=True)
    external_id = Column(String(255), nullable=True)
    title = Column(String(512), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    thumbnail_url = Column(String(2048), nullable=True)
    status = Column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    # JSON: list of {"start": float, "end": float, "text": str}
    transcript = Column(JSON, nullable=True)
    language = Column(String(16), nullable=True)
    error_message = Column(Text, nullable=True)

    user = relationship("User", back_populates="projects")
    shorts = relationship(
        "Short",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'fetching', 'transcribing', 'analyzing', 'ready', 'failed')",
            name="ck_projects_status",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Project id={self.id} status={self.status!r}>"
