"""RenderJob model - one queued/executed video render for a Short."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, CreatedAtMixin

RENDER_JOB_STATUSES = ("queued", "processing", "completed", "failed", "cancelled")
RENDER_JOB_STAGES = (
    "downloading",
    "trimming",
    "broll",
    "captions",
    "encoding",
    "uploading",
)


class RenderJob(Base, CreatedAtMixin):
    __tablename__ = "render_jobs"

    id = Column(Integer, primary_key=True)
    short_id = Column(
        Integer,
        ForeignKey("shorts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    progress = Column(Integer, nullable=False, default=0, server_default="0")
    stage = Column(String(32), nullable=True)
    output_url = Column(String(2048), nullable=True)
    output_format = Column(String(16), nullable=False, default="mp4", server_default="mp4")
    video_codec = Column(String(16), nullable=False, default="h264", server_default="h264")
    audio_codec = Column(String(16), nullable=False, default="aac", server_default="aac")
    resolution = Column(
        String(16), nullable=False, default="1080x1920", server_default="1080x1920"
    )
    aspect_ratio = Column(
        String(16), nullable=False, default="9:16", server_default="9:16"
    )
    file_size_bytes = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    short = relationship("Short", back_populates="render_jobs")
    user = relationship("User", back_populates="render_jobs")

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_render_jobs_status",
        ),
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_render_jobs_progress_range",
        ),
        CheckConstraint(
            "stage IS NULL OR stage IN ('downloading', 'trimming', 'broll', "
            "'captions', 'encoding', 'uploading')",
            name="ck_render_jobs_stage",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RenderJob id={self.id} short_id={self.short_id} status={self.status!r}>"
