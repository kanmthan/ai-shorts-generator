"""Canonical master-format export schema for Shorts Analysis.

These models mirror the master JSON structure from ``INITIAL.md`` **exactly**.
Claude's raw analysis output is parsed and validated against
:class:`ShortsExportEnvelope` before anything is persisted, and the same models
are re-serialised by ``GET /api/v1/shorts/{id}/export.json``.

Nothing here touches the database - it is a pure data contract / trust boundary
for LLM output.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "SourceVideoOut",
    "ScoresOut",
    "EditingOut",
    "BrollExport",
    "SubtitleExport",
    "ShortExport",
    "ShortsExportEnvelope",
]

# Envelope-level status values the master format allows.
EXPORT_STATUSES = ("success", "partial", "error")


class _Base(BaseModel):
    """Shared config: ignore unknown keys so a slightly chatty model still validates."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        from_attributes=True,
    )


class SourceVideoOut(_Base):
    """``source_video`` block - the long-form video the shorts were cut from."""

    url: str
    title: str | None = None
    duration_seconds: int = Field(0, ge=0)


class ScoresOut(_Base):
    """Nine 1-10 metrics plus a float ``overall``."""

    hook_strength: float = Field(..., ge=1, le=10)
    standalone_value: float = Field(..., ge=1, le=10)
    engagement: float = Field(..., ge=1, le=10)
    retention: float = Field(..., ge=1, le=10)
    payoff: float = Field(..., ge=1, le=10)
    clarity: float = Field(..., ge=1, le=10)
    shareability: float = Field(..., ge=1, le=10)
    viral_potential: float = Field(..., ge=1, le=10)
    b_roll_quality: float = Field(..., ge=1, le=10)
    overall: float = Field(..., ge=0, le=10)


class EditingOut(_Base):
    """``editing`` directives block."""

    aspect_ratio: str = "9:16"
    resolution: str = "1080x1920"
    format: str = "mp4"
    remove_silence: bool = True
    add_captions: bool = True
    caption_style: str = "word_by_word"
    add_zoom_effects: bool = True
    add_b_roll: bool = True
    b_roll_position: str = "middle"
    music: str = "none"


class BrollExport(_Base):
    """One planned B-roll cutaway, master-format shape.

    ``start`` / ``end`` are ``MM:SS`` **relative to the short**;
    ``original_start`` / ``original_end`` are ``MM:SS`` in the source video.
    """

    start: str
    end: str
    original_start: str | None = None
    original_end: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    description: str | None = None
    reason: str | None = None
    search_keywords: list[str] = Field(default_factory=list)
    type: str | None = None
    transition: str | None = None
    placement: str | None = None
    use_broll: bool = True


class SubtitleExport(_Base):
    """One subtitle line, ``MM:SS`` times relative to the short."""

    start: str
    end: str
    text: str
    highlight_words: list[str] | None = None


class ShortExport(_Base):
    """One short in the master export format."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        from_attributes=True,
        coerce_numbers_to_str=True,
    )

    id: str
    start_time: str
    end_time: str
    duration_seconds: int = Field(..., ge=0)
    title: str
    hook: str | None = None
    summary: str | None = None
    reason: str | None = None
    scores: ScoresOut
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    editing: EditingOut = Field(default_factory=EditingOut)
    broll_segments: list[BrollExport] = Field(default_factory=list, min_length=1)
    subtitle_segments: list[SubtitleExport] = Field(default_factory=list)


class ShortsExportEnvelope(_Base):
    """Top-level master JSON object returned by the analysis / export layer."""

    status: str = Field("success", description="success | partial | error")
    source_video: SourceVideoOut
    total_shorts: int = Field(0, ge=0)
    shorts: list[ShortExport] = Field(default_factory=list)
    error: str | None = None
