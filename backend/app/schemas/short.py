"""Pydantic v2 schemas for the Shorts Analysis module (DB <-> API contracts).

* ``*Out`` models serialise SQLAlchemy rows for API responses
  (``from_attributes=True``).
* ``*In`` models are the internal shape used when persisting analysis output.
* :class:`ShortUpdate` is the PATCH payload for manual tweaks.

The canonical master-format export lives in :mod:`app.schemas.export`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "BrollSegmentIn",
    "BrollSegmentOut",
    "SubtitleSegmentIn",
    "SubtitleSegmentOut",
    "BrollTimelineItem",
    "ShortOut",
    "ShortCardOut",
    "ShortUpdate",
]


# --------------------------------------------------------------------------- #
# B-roll                                                                      #
# --------------------------------------------------------------------------- #
class BrollSegmentIn(BaseModel):
    """Internal shape for persisting one planned B-roll segment."""

    model_config = ConfigDict(extra="ignore")

    start: str
    end: str
    original_start: str | None = None
    original_end: str | None = None
    duration_seconds: float | None = None
    description: str | None = None
    reason: str | None = None
    search_keywords: list[str] = Field(default_factory=list)
    type: str | None = None
    transition: str | None = None
    placement: str | None = None
    use_broll: bool = True


def _none_to_list(value: Any) -> Any:
    """Coerce a nullable JSON column into an empty list for list-typed fields."""
    return [] if value is None else value


class BrollSegmentOut(BaseModel):
    """One B-roll segment as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    short_id: int
    start: str
    end: str
    original_start: str | None = None
    original_end: str | None = None
    duration_seconds: float | None = None
    description: str | None = None
    reason: str | None = None
    search_keywords: list[str] = Field(default_factory=list)
    type: str | None = None
    transition: str | None = None
    placement: str | None = None
    use_broll: bool = True
    asset_url: str | None = None
    asset_source: str | None = None
    asset_status: str = "pending"

    _fix_keywords = field_validator("search_keywords", mode="before")(_none_to_list)


# --------------------------------------------------------------------------- #
# Subtitles                                                                   #
# --------------------------------------------------------------------------- #
class SubtitleSegmentIn(BaseModel):
    """Internal shape for persisting one subtitle line."""

    model_config = ConfigDict(extra="ignore")

    start: str
    end: str
    text: str
    highlight_words: list[str] | None = None


class SubtitleSegmentOut(BaseModel):
    """One subtitle line as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    short_id: int
    start: str
    end: str
    text: str
    highlight_words: list[str] | None = None


# --------------------------------------------------------------------------- #
# Short                                                                       #
# --------------------------------------------------------------------------- #
class BrollTimelineItem(BaseModel):
    """Compact B-roll entry for the shorts-board card timeline."""

    model_config = ConfigDict(from_attributes=True)

    start: str
    end: str
    placement: str | None = None
    description: str | None = None
    type: str | None = None
    use_broll: bool = True
    asset_status: str = "pending"


class ShortOut(BaseModel):
    """Full short detail: scores, editing, B-roll and subtitle segments."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    index: int
    start_time: str
    end_time: str
    duration_seconds: float | None = None
    title: str | None = None
    hook: str | None = None
    summary: str | None = None
    reason: str | None = None
    scores: dict[str, float] | None = None
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    editing: dict[str, object] | None = None
    category: str | None = None
    status: str = "draft"
    created_at: datetime | None = None
    broll_segments: list[BrollSegmentOut] = Field(default_factory=list)
    subtitle_segments: list[SubtitleSegmentOut] = Field(default_factory=list)

    _fix_hashtags = field_validator("hashtags", mode="before")(_none_to_list)


class ShortCardOut(BaseModel):
    """Preview payload for ``GET /api/v1/projects/{id}/shorts`` (ShortCard)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    index: int
    title: str | None = None
    duration_seconds: float | None = None
    start_time: str
    end_time: str
    hook: str | None = None
    summary: str | None = None
    overall_score: float | None = None
    engagement_score: float | None = None
    viral_potential: float | None = None
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    status: str = "draft"
    broll_timeline: list[BrollTimelineItem] = Field(default_factory=list)

    @classmethod
    def from_model(cls, short: Any) -> ShortCardOut:
        """Build a card from a SQLAlchemy ``Short`` (with ``broll_segments`` loaded)."""
        scores = short.scores or {}
        segments = short.broll_segments or []
        return cls(
            id=short.id,
            project_id=short.project_id,
            index=short.index,
            title=short.title,
            duration_seconds=short.duration_seconds,
            start_time=short.start_time,
            end_time=short.end_time,
            hook=short.hook,
            summary=short.summary,
            overall_score=_num(scores.get("overall")),
            engagement_score=_num(scores.get("engagement")),
            viral_potential=_num(scores.get("viral_potential")),
            caption=short.caption,
            hashtags=list(short.hashtags or []),
            status=short.status,
            broll_timeline=[BrollTimelineItem.model_validate(seg) for seg in segments],
        )


class ShortUpdate(BaseModel):
    """PATCH payload - every field optional."""

    model_config = ConfigDict(extra="forbid")

    start_time: str | None = None
    end_time: str | None = None
    title: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None


def _num(value: object) -> float | None:
    """Best-effort float coercion for score values coming out of JSON."""
    if isinstance(value, (int | float)):
        return float(value)
    return None
