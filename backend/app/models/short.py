"""Short-form clip models: Short, BrollSegment and SubtitleSegment."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, CreatedAtMixin

# --- allowed value sets ------------------------------------------------------
SHORT_STATUSES = ("draft", "queued", "rendering", "rendered", "failed")

BROLL_TYPES = (
    "stock_video",
    "image",
    "screenshot",
    "screen_recording",
    "chart",
    "animation",
    "news_image",
    "original_cutaway",
)
BROLL_TRANSITIONS = ("smooth_cut", "quick_cut", "fade", "dissolve")
BROLL_PLACEMENTS = ("start", "middle", "end")
BROLL_ASSET_SOURCES = ("pexels", "pixabay", "original")
BROLL_ASSET_STATUSES = ("pending", "fetched", "not_found", "skipped")


class Short(Base, CreatedAtMixin):
    __tablename__ = "shorts"

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    index = Column(Integer, nullable=False)
    start_time = Column(String(16), nullable=False)  # HH:MM:SS
    end_time = Column(String(16), nullable=False)  # HH:MM:SS
    duration_seconds = Column(Float, nullable=True)
    title = Column(String(512), nullable=True)
    hook = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    # JSON: 9 metrics rated 1-10 plus an "overall" float.
    scores = Column(JSON, nullable=True)
    caption = Column(Text, nullable=True)
    hashtags = Column(JSON, nullable=True)  # JSON list[str]
    editing = Column(JSON, nullable=True)  # JSON editing directives
    category = Column(String(100), nullable=True)
    status = Column(
        String(32),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    project = relationship("Project", back_populates="shorts")
    broll_segments = relationship(
        "BrollSegment",
        back_populates="short",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BrollSegment.id",
    )
    subtitle_segments = relationship(
        "SubtitleSegment",
        back_populates="short",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SubtitleSegment.id",
    )
    render_jobs = relationship(
        "RenderJob",
        back_populates="short",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'queued', 'rendering', 'rendered', 'failed')",
            name="ck_shorts_status",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Short id={self.id} project_id={self.project_id} index={self.index}>"


class BrollSegment(Base):
    __tablename__ = "broll_segments"

    id = Column(Integer, primary_key=True)
    short_id = Column(
        Integer,
        ForeignKey("shorts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start = Column(String(16), nullable=False)  # MM:SS relative to the short
    end = Column(String(16), nullable=False)  # MM:SS relative to the short
    original_start = Column(String(16), nullable=True)
    original_end = Column(String(16), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    search_keywords = Column(JSON, nullable=True)  # JSON list[str]
    type = Column(String(32), nullable=True)
    transition = Column(String(32), nullable=True)
    placement = Column(String(16), nullable=True)
    use_broll = Column(Boolean, nullable=False, default=True, server_default="true")
    asset_url = Column(String(2048), nullable=True)
    asset_source = Column(String(32), nullable=True)
    asset_status = Column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    short = relationship("Short", back_populates="broll_segments")

    __table_args__ = (
        CheckConstraint(
            "type IS NULL OR type IN ('stock_video', 'image', 'screenshot', "
            "'screen_recording', 'chart', 'animation', 'news_image', 'original_cutaway')",
            name="ck_broll_segments_type",
        ),
        CheckConstraint(
            "transition IS NULL OR transition IN "
            "('smooth_cut', 'quick_cut', 'fade', 'dissolve')",
            name="ck_broll_segments_transition",
        ),
        CheckConstraint(
            "placement IS NULL OR placement IN ('start', 'middle', 'end')",
            name="ck_broll_segments_placement",
        ),
        CheckConstraint(
            "asset_source IS NULL OR asset_source IN ('pexels', 'pixabay', 'original')",
            name="ck_broll_segments_asset_source",
        ),
        CheckConstraint(
            "asset_status IN ('pending', 'fetched', 'not_found', 'skipped')",
            name="ck_broll_segments_asset_status",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<BrollSegment id={self.id} short_id={self.short_id} placement={self.placement!r}>"


class SubtitleSegment(Base):
    __tablename__ = "subtitle_segments"

    id = Column(Integer, primary_key=True)
    short_id = Column(
        Integer,
        ForeignKey("shorts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start = Column(String(16), nullable=False)  # MM:SS relative to the short
    end = Column(String(16), nullable=False)  # MM:SS relative to the short
    text = Column(Text, nullable=False)
    highlight_words = Column(JSON, nullable=True)  # JSON list[str], nullable

    short = relationship("Short", back_populates="subtitle_segments")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<SubtitleSegment id={self.id} short_id={self.short_id}>"
