"""Pydantic v2 schemas for the Rendering & Export module.

Request/response contracts for ``app.routers.render_jobs``. ``RenderJobOut``
mirrors every column on :class:`~app.models.render_job.RenderJob`;
``RenderJobListItem`` is the trimmed row used by the list endpoint;
``RenderEnqueueResponse`` is the 202 body returned when a render is queued.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "RenderJobOut",
    "RenderJobListItem",
    "RenderEnqueueResponse",
]


class RenderJobOut(BaseModel):
    """Full render-job detail (polled by the UI progress modal)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    short_id: int
    user_id: int
    status: str
    progress: int = Field(0, ge=0, le=100)
    stage: str | None = None
    output_url: str | None = None
    output_format: str = "mp4"
    video_codec: str = "h264"
    audio_codec: str = "aac"
    resolution: str = "1080x1920"
    aspect_ratio: str = "9:16"
    file_size_bytes: int | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class RenderJobListItem(BaseModel):
    """Lightweight row for ``GET /api/v1/render-jobs`` (newest first)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    short_id: int
    status: str
    progress: int = Field(0, ge=0, le=100)
    stage: str | None = None
    output_url: str | None = None
    file_size_bytes: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class RenderEnqueueResponse(BaseModel):
    """Body returned by ``POST /api/v1/shorts/{short_id}/render`` (HTTP 202)."""

    job_id: int
    status: str
