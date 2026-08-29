"""Video metadata ingestion via the ``yt-dlp`` Python API.

No shelling out - we import :mod:`yt_dlp` and call it in-process with
``skip_download=True``. Only lightweight metadata is pulled (title, duration,
id, platform/extractor, thumbnail). Duration is checked against
``settings.MAX_VIDEO_DURATION_SECONDS``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.exceptions import ExternalServiceError, ValidationError
from app.logging_config import get_logger

__all__ = ["VideoMeta", "fetch_metadata"]

logger = get_logger("services.ingestion")


@dataclass(slots=True)
class VideoMeta:
    """Normalised subset of a video's metadata."""

    url: str
    video_id: str
    title: str
    duration_seconds: int | None
    platform: str
    thumbnail_url: str | None


_YDL_OPTS: dict[str, object] = {
    "skip_download": True,
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "socket_timeout": 30,
    # Never let yt-dlp write anything to disk during metadata probing.
    "writesubtitles": False,
    "writeautomaticsub": False,
    "writethumbnail": False,
}


def fetch_metadata(url: str) -> VideoMeta:
    """Fetch metadata for ``url`` without downloading the media.

    Args:
        url: A pre-validated public video URL.

    Returns:
        A :class:`VideoMeta`.

    Raises:
        ValidationError: If the video is longer than the configured maximum.
        ExternalServiceError: If yt-dlp cannot extract metadata for the URL.
    """
    try:
        import yt_dlp  # imported lazily so the API process need not carry it
        from yt_dlp.utils import DownloadError, ExtractorError
    except ImportError as exc:  # pragma: no cover - worker image always has it
        raise ExternalServiceError("yt-dlp is not installed in this environment") from exc

    try:
        with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
    except (DownloadError, ExtractorError) as exc:
        logger.info("yt-dlp failed to extract %s: %s", url, exc)
        raise ExternalServiceError(f"Could not read video metadata: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected yt-dlp error for %s", url)
        raise ExternalServiceError(f"Video metadata lookup failed: {exc}") from exc

    if not isinstance(info, dict):
        raise ExternalServiceError("yt-dlp returned no metadata for this URL")

    # A playlist / channel URL slipped through - take the first entry if present.
    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if isinstance(e, dict)]
        if not entries:
            raise ExternalServiceError("URL points to an empty playlist")
        info = entries[0]

    raw_duration = info.get("duration")
    duration_seconds: int | None
    try:
        duration_seconds = int(raw_duration) if raw_duration is not None else None
    except (TypeError, ValueError):
        duration_seconds = None

    max_seconds = settings.MAX_VIDEO_DURATION_SECONDS
    if duration_seconds is not None and duration_seconds > max_seconds:
        raise ValidationError(
            f"Video is {duration_seconds}s long; the maximum allowed is {max_seconds}s"
        )

    platform = (
        info.get("extractor_key")
        or info.get("extractor")
        or info.get("webpage_url_domain")
        or "unknown"
    )

    meta = VideoMeta(
        url=info.get("webpage_url") or url,
        video_id=str(info.get("id") or ""),
        title=info.get("title") or "Untitled",
        duration_seconds=duration_seconds,
        platform=str(platform).lower(),
        thumbnail_url=info.get("thumbnail"),
    )
    logger.info(
        "Fetched metadata: id=%s platform=%s duration=%s",
        meta.video_id,
        meta.platform,
        meta.duration_seconds,
    )
    return meta
