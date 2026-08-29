"""Shorts analysis orchestration.

:func:`run_analysis` is the seam between the Celery task and the LLM client:

1. loads the ``Project`` and requires a transcript,
2. asks :class:`app.services.llm.AnthropicClient` for a validated
   :class:`~app.schemas.export.ShortsExportEnvelope`,
3. clamps / rejects shorts whose duration or timestamps fall outside the
   configured tolerance band,
4. replaces any existing ``Short`` rows for the project and persists the new
   ``Short`` + ``BrollSegment`` + ``SubtitleSegment`` graph,
5. returns ``{"created": <int>, "partial": <bool>}``.

All Claude output is validated (step 2) *before* anything is written.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import NotFoundError, ValidationError
from app.logging_config import get_logger
from app.models import (
    BROLL_PLACEMENTS,
    BROLL_TRANSITIONS,
    BROLL_TYPES,
    BrollSegment,
    Project,
    Short,
    SubtitleSegment,
)
from app.schemas.export import BrollExport, ShortExport, SubtitleExport
from app.services.llm import PROMPT_VERSION, AnthropicClient

logger = get_logger("services.analysis")

__all__ = ["run_analysis"]


def run_analysis(db: Session, project_id: int) -> dict[str, Any]:
    """Run Claude analysis for ``project_id`` and persist the resulting shorts.

    Args:
        db: Database session (owned by the caller / task).
        project_id: Project to analyse; must be past ingestion with a transcript.

    Returns:
        ``{"created": <int>, "partial": <bool>}`` - ``partial`` is ``True`` when
        fewer than 5 valid shorts were persisted.

    Raises:
        NotFoundError: Unknown project.
        ValidationError: The project has no transcript to analyse.
        ExternalServiceError: Claude is unreachable / returns non-conforming JSON.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise NotFoundError("Project")

    transcript = project.transcript
    if not transcript or not isinstance(transcript, list):
        raise ValidationError("Project has no transcript to analyse")

    client = AnthropicClient(prompt_version=PROMPT_VERSION)
    envelope = client.analyze_transcript(project, transcript)
    logger.info(
        "Claude returned status=%s candidates=%d for project %s",
        envelope.status,
        len(envelope.shorts),
        project_id,
    )

    video_duration = project.duration_seconds
    lo = max(0.0, float(settings.SHORT_MIN_SECONDS) - 5.0)
    hi = float(settings.SHORT_MAX_SECONDS) + 5.0

    # Regenerate semantics: drop existing shorts (cascades to segments) first.
    deleted = (
        db.query(Short)
        .filter(Short.project_id == project_id)
        .delete(synchronize_session=False)
    )
    if deleted:
        logger.info("Cleared %d existing shorts for project %s", deleted, project_id)

    created = 0
    for candidate in envelope.shorts:
        bounds = _clamped_bounds(candidate, video_duration, lo, hi)
        if bounds is None:
            logger.info(
                "Rejected short %s (start=%s end=%s) - outside tolerance band",
                candidate.id,
                candidate.start_time,
                candidate.end_time,
            )
            continue

        start_s, end_s = bounds
        created += 1
        short = Short(
            project_id=project_id,
            index=created,
            start_time=_fmt_hhmmss(start_s),
            end_time=_fmt_hhmmss(end_s),
            duration_seconds=round(end_s - start_s, 2),
            title=candidate.title,
            hook=candidate.hook,
            summary=candidate.summary,
            reason=candidate.reason,
            scores=candidate.scores.model_dump(),
            caption=candidate.caption,
            hashtags=list(candidate.hashtags),
            editing=candidate.editing.model_dump(),
            category=None,
            status="draft",
        )
        short.broll_segments = [_broll_row(seg) for seg in candidate.broll_segments]
        short.subtitle_segments = [
            _subtitle_row(seg) for seg in candidate.subtitle_segments
        ]
        db.add(short)

    db.commit()
    partial = created < 5
    logger.info(
        "Persisted %d shorts for project %s (partial=%s)", created, project_id, partial
    )
    return {"created": created, "partial": partial}


# --------------------------------------------------------------------------- #
# Clamping / validation helpers                                               #
# --------------------------------------------------------------------------- #
def _clamped_bounds(
    short: ShortExport,
    video_duration: int | None,
    lo: float,
    hi: float,
) -> tuple[float, float] | None:
    """Return clamped ``(start_s, end_s)`` or ``None`` if the short is invalid."""
    start_s = _parse_ts(short.start_time)
    end_s = _parse_ts(short.end_time)
    if start_s is None or end_s is None:
        return None

    start_s = max(0.0, start_s)
    end_s = max(0.0, end_s)
    if video_duration is not None and video_duration > 0:
        start_s = min(start_s, float(video_duration))
        end_s = min(end_s, float(video_duration))

    if end_s <= start_s:
        return None

    duration = end_s - start_s
    if duration < lo or duration > hi:
        return None
    return start_s, end_s


def _sanitize(value: str | None, allowed: tuple[str, ...]) -> str | None:
    """Return ``value`` only if it is in ``allowed`` (matches DB CHECK constraints)."""
    return value if value in allowed else None


def _broll_row(seg: BrollExport) -> BrollSegment:
    """Map a validated :class:`BrollExport` to a :class:`BrollSegment` row."""
    return BrollSegment(
        start=seg.start,
        end=seg.end,
        original_start=seg.original_start,
        original_end=seg.original_end,
        duration_seconds=seg.duration_seconds,
        description=seg.description,
        reason=seg.reason,
        search_keywords=list(seg.search_keywords),
        type=_sanitize(seg.type, BROLL_TYPES),
        transition=_sanitize(seg.transition, BROLL_TRANSITIONS),
        placement=_sanitize(seg.placement, BROLL_PLACEMENTS),
        use_broll=bool(seg.use_broll),
        asset_status="pending",
    )


def _subtitle_row(seg: SubtitleExport) -> SubtitleSegment:
    """Map a validated :class:`SubtitleExport` to a :class:`SubtitleSegment` row."""
    return SubtitleSegment(
        start=seg.start,
        end=seg.end,
        text=seg.text,
        highlight_words=list(seg.highlight_words) if seg.highlight_words else None,
    )


def _parse_ts(value: str | None) -> float | None:
    """Parse ``HH:MM:SS`` / ``MM:SS`` / ``SS`` (optionally fractional) to seconds."""
    if not value or not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if not 1 <= len(parts) <= 3:
        return None
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    seconds = 0.0
    for num in nums:
        seconds = seconds * 60.0 + num
    return seconds if seconds >= 0 else None


def _fmt_hhmmss(seconds: float) -> str:
    """Format a second count as ``HH:MM:SS`` (whole seconds)."""
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
