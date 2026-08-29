"""Pydantic v2 schemas for the Projects & Video Ingestion module.

These describe the request/response contracts for ``app.routers.projects``.
The full transcript array is *never* serialised back to the client - callers get
a summary (segment count + language) instead; the raw transcript is an internal
artefact consumed by the analysis pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

__all__ = [
    "ProjectCreate",
    "ProjectOut",
    "ProjectListItem",
    "ProjectStatusOut",
    "Paginated",
    "progress_for_status",
]

T = TypeVar("T")

# Coarse "how far along the pipeline" hint, keyed by Project.status.
_STATUS_PROGRESS: dict[str, int] = {
    "pending": 5,
    "fetching": 25,
    "transcribing": 55,
    "analyzing": 80,
    "ready": 100,
    "failed": 0,
}


def progress_for_status(status: str | None) -> int:
    """Return a 0-100 progress hint for a project ``status``."""
    return _STATUS_PROGRESS.get(status or "", 0)


class ProjectCreate(BaseModel):
    """Payload for ``POST /api/v1/projects``."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl = Field(..., description="Public long-form video URL to ingest.")


class ProjectOut(BaseModel):
    """Full project detail. ``transcript`` is summarised, never inlined."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    url: str
    platform: str | None = None
    external_id: str | None = None
    title: str | None = None
    duration_seconds: int | None = None
    thumbnail_url: str | None = None
    status: str
    language: str | None = None
    transcript_segment_count: int = Field(
        0, description="Number of normalised transcript segments stored."
    )
    error_message: str | None = None
    progress: int = Field(0, ge=0, le=100, description="Coarse pipeline progress hint.")
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_model(cls, project: object) -> ProjectOut:
        """Build from a SQLAlchemy ``Project`` instance, summarising transcript."""
        transcript = getattr(project, "transcript", None)
        count = len(transcript) if isinstance(transcript, list) else 0
        status = getattr(project, "status", None)
        return cls(
            id=project.id,
            user_id=project.user_id,
            url=project.url,
            platform=getattr(project, "platform", None),
            external_id=getattr(project, "external_id", None),
            title=getattr(project, "title", None),
            duration_seconds=getattr(project, "duration_seconds", None),
            thumbnail_url=getattr(project, "thumbnail_url", None),
            status=status,
            language=getattr(project, "language", None),
            transcript_segment_count=count,
            error_message=getattr(project, "error_message", None),
            progress=progress_for_status(status),
            created_at=getattr(project, "created_at", None),
            updated_at=getattr(project, "updated_at", None),
        )


class ProjectListItem(BaseModel):
    """Lightweight row for the paginated project list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str | None = None
    platform: str | None = None
    status: str
    duration_seconds: int | None = None
    thumbnail_url: str | None = None
    progress: int = Field(0, ge=0, le=100)
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: object) -> ProjectListItem:
        """Build from a SQLAlchemy ``Row`` / mapping produced by ``with_entities``."""
        data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)  # type: ignore[attr-defined]
        data["progress"] = progress_for_status(data.get("status"))
        return cls(**data)


class ProjectStatusOut(BaseModel):
    """Cheap polling payload for ``GET /api/v1/projects/{id}/status``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    error_message: str | None = None
    progress: int = Field(0, ge=0, le=100)

    @classmethod
    def from_row(cls, row: object) -> ProjectStatusOut:
        data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)  # type: ignore[attr-defined]
        data["progress"] = progress_for_status(data.get("status"))
        return cls(**data)


class Paginated(BaseModel, Generic[T]):
    """Generic pagination envelope."""

    items: list[T]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    pages: int = Field(..., ge=0)

    @classmethod
    def build(
        cls, items: list[T], *, total: int, page: int, page_size: int
    ) -> Paginated[T]:
        pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)
