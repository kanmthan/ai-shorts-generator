"""Caption transcript extraction for a submitted video.

``fetch_transcript`` returns the video's caption transcript normalised to a flat
list of ``{"start": float, "end": float, "text": str}`` segments (seconds).

Two strategies are tried, in order:

1. :mod:`youtube_transcript_api` - fast, no media probing, YouTube only.
2. ``yt-dlp`` subtitle / automatic-caption tracks - works for every extractor
   yt-dlp supports; the chosen track is downloaded in-process and parsed
   (``json3`` / ``vtt`` / ``srv*`` / ``ttml``).

If neither yields captions an :class:`~app.exceptions.ExternalServiceError` is
raised - per the PRP, "no captions" fails the project with a clear message
(Whisper fallback is explicitly post-MVP).
"""

from __future__ import annotations

import html
import json
import re
import urllib.request
from typing import Any

from app.exceptions import ExternalServiceError
from app.logging_config import get_logger

__all__ = ["fetch_transcript", "TranscriptSegments"]

logger = get_logger("services.transcript")

_HTTP_TIMEOUT = 30
_PREFERRED_LANGS: tuple[str, ...] = ("en", "en-US", "en-GB")
_SUPPORTED_SUB_EXTS: tuple[str, ...] = ("json3", "srv3", "srv2", "srv1", "vtt", "ttml", "srt")
_TS_RE = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})")
_CUE_RE = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})"
)
_TAG_RE = re.compile(r"<[^>]+>")


class TranscriptSegments(list):
    """A ``list[dict]`` of ``{start, end, text}`` plus a detected ``language``.

    Subclasses :class:`list` so it satisfies the documented ``-> list[dict]``
    return type (and any ``isinstance(x, list)`` check / JSON serialisation),
    while letting the ingestion task read ``segments.language``.
    """

    language: str | None = None


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #
def fetch_transcript(url: str, video_id: str, platform: str) -> list[dict]:
    """Fetch and normalise the caption transcript for a video.

    Args:
        url: The (already SSRF-validated) public video URL.
        video_id: Extractor video id from :func:`app.services.ingestion.fetch_metadata`.
        platform: Lower-cased extractor/platform key (informational only).

    Returns:
        A :class:`TranscriptSegments` (a ``list[dict]``) ordered by ``start``,
        each item ``{"start": float, "end": float, "text": str}``. The detected
        caption language, when known, is available as ``result.language``.

    Raises:
        ExternalServiceError: If no captions can be obtained for the video.
    """
    logger.info("Fetching transcript: video_id=%s platform=%s", video_id, platform)

    segments = _try_youtube_transcript_api(video_id)
    if not segments:
        segments = _try_ytdlp_subtitles(url)

    if not segments:
        raise ExternalServiceError("No captions available for this video")

    # In-place tidy so the TranscriptSegments instance (and .language) survives.
    segments[:] = sorted(
        (s for s in segments if s.get("text")), key=lambda s: s["start"]
    )
    if not segments:
        raise ExternalServiceError("No captions available for this video")

    logger.info(
        "Transcript ready: %d segments, language=%s",
        len(segments),
        getattr(segments, "language", None),
    )
    return segments


# --------------------------------------------------------------------------- #
# Strategy 1: youtube-transcript-api
# --------------------------------------------------------------------------- #
def _try_youtube_transcript_api(video_id: str) -> TranscriptSegments | None:
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        logger.warning("youtube-transcript-api not installed; skipping strategy 1")
        return None

    try:
        # New (>=1.0) instance API.
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        chosen = _pick_transcript(transcript_list)
        if chosen is None:
            return None
        fetched = chosen.fetch()
        language = getattr(chosen, "language_code", None)
        raw_iter: Any = fetched
    except AttributeError:
        # Old (<=0.6.x) class-method API.
        try:
            raw_iter = YouTubeTranscriptApi.get_transcript(video_id)  # type: ignore[attr-defined]
            language = None
        except Exception as exc:
            logger.info("youtube-transcript-api (legacy) failed for %s: %s", video_id, exc)
            return None
    except Exception as exc:
        logger.info("youtube-transcript-api could not fetch %s: %s", video_id, exc)
        return None

    out = TranscriptSegments()
    out.language = language
    for snip in raw_iter:
        if isinstance(snip, dict):
            start = _as_float(snip.get("start"))
            dur = _as_float(snip.get("duration"))
            text = str(snip.get("text") or "").strip()
        else:
            start = _as_float(getattr(snip, "start", None))
            dur = _as_float(getattr(snip, "duration", None))
            text = str(getattr(snip, "text", "") or "").strip()
        if not text:
            continue
        out.append({"start": start, "end": round(start + dur, 3), "text": text})

    if not out:
        return None
    logger.info("Strategy 1 (youtube-transcript-api) yielded %d segments", len(out))
    return out


def _pick_transcript(transcript_list: Any) -> Any | None:
    """Prefer manually-created English, then any manual, then generated."""
    manual: list[Any] = []
    generated: list[Any] = []
    try:
        for tr in transcript_list:
            (generated if getattr(tr, "is_generated", False) else manual).append(tr)
    except TypeError:
        return None

    for group in (manual, generated):
        for lang in _PREFERRED_LANGS:
            for tr in group:
                code = str(getattr(tr, "language_code", "")).lower()
                if code.startswith(lang.lower()):
                    return tr
        if group:
            return group[0]
    return None


# --------------------------------------------------------------------------- #
# Strategy 2: yt-dlp subtitle tracks
# --------------------------------------------------------------------------- #
def _try_ytdlp_subtitles(url: str) -> TranscriptSegments | None:
    try:
        import yt_dlp
        from yt_dlp.utils import DownloadError, ExtractorError
    except ImportError:
        logger.warning("yt-dlp not installed; skipping strategy 2")
        return None

    opts: dict[str, object] = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "writesubtitles": False,
        "writeautomaticsub": False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except (DownloadError, ExtractorError) as exc:
        logger.info("yt-dlp subtitle probe failed for %s: %s", url, exc)
        return None
    except Exception:
        logger.exception("Unexpected yt-dlp error probing subtitles for %s", url)
        return None

    if not isinstance(info, dict):
        return None
    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if isinstance(e, dict)]
        if not entries:
            return None
        info = entries[0]

    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    for label, source in (("manual", manual), ("auto", auto)):
        if not isinstance(source, dict) or not source:
            continue
        lang, tracks = _pick_subtitle_track(source)
        downloaded = _download_first_supported(tracks)
        if downloaded is None:
            continue
        ext, body = downloaded
        segs = _parse_subtitles(body, ext)
        if segs:
            result = TranscriptSegments(segs)
            result.language = lang
            logger.info(
                "Strategy 2 (yt-dlp %s subs) yielded %d segments (%s/%s)",
                label,
                len(segs),
                lang,
                ext,
            )
            return result
    return None


def _pick_subtitle_track(source: dict[str, Any]) -> tuple[str | None, list[dict]]:
    for lang in _PREFERRED_LANGS:
        for key in source:
            if str(key).lower().startswith(lang.lower()):
                return key, list(source.get(key) or [])
    key = next(iter(source))
    return key, list(source.get(key) or [])


def _download_first_supported(tracks: list[dict]) -> tuple[str, str] | None:
    candidates = [
        t for t in tracks if isinstance(t, dict) and t.get("url")
    ]
    candidates.sort(
        key=lambda t: _SUPPORTED_SUB_EXTS.index(t["ext"])
        if t.get("ext") in _SUPPORTED_SUB_EXTS
        else len(_SUPPORTED_SUB_EXTS)
    )
    for track in candidates:
        ext = str(track.get("ext") or "").lower()
        try:
            req = urllib.request.Request(
                track["url"], headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            logger.info("Failed to download subtitle track (%s): %s", ext, exc)
            continue
        if body.strip():
            return ext or "vtt", body
    return None


# --------------------------------------------------------------------------- #
# Subtitle format parsers
# --------------------------------------------------------------------------- #
def _parse_subtitles(body: str, fmt: str) -> list[dict]:
    fmt = (fmt or "").lower()
    parsers: list[Any]
    if fmt == "json3":
        parsers = [_parse_json3]
    elif fmt in ("vtt", "srt"):
        parsers = [_parse_vtt]
    elif fmt in ("srv1", "srv2", "srv3", "ttml"):
        parsers = [_parse_timed_xml, _parse_vtt]
    else:
        parsers = [_parse_json3, _parse_vtt, _parse_timed_xml]

    for parser in parsers:
        try:
            segs = parser(body)
        except Exception as exc:
            logger.debug("Subtitle parser %s failed: %s", parser.__name__, exc)
            continue
        if segs:
            return segs
    return []


def _parse_json3(body: str) -> list[dict]:
    data = json.loads(body)
    out: list[dict] = []
    for event in data.get("events") or []:
        start_ms = event.get("tStartMs")
        segs = event.get("segs") or []
        if start_ms is None or not segs:
            continue
        text = "".join(str(s.get("utf8", "")) for s in segs).strip()
        if not text:
            continue
        start = start_ms / 1000.0
        dur = (event.get("dDurationMs") or 0) / 1000.0
        out.append(
            {"start": round(start, 3), "end": round(start + dur, 3), "text": text}
        )
    return _dedupe(out)


def _parse_vtt(body: str) -> list[dict]:
    text = body.replace("\r\n", "\n").replace("\r", "\n")
    out: list[dict] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        cue = None
        text_start = 0
        for idx, line in enumerate(lines):
            match = _CUE_RE.search(line)
            if match:
                cue = match
                text_start = idx + 1
                break
        if cue is None:
            continue
        start_m = _TS_RE.match(cue.group(1))
        end_m = _TS_RE.match(cue.group(2))
        if not start_m or not end_m:
            continue
        start = _hms_to_seconds(*start_m.groups())
        end = _hms_to_seconds(*end_m.groups())
        cue_text = " ".join(
            _clean_text(line) for line in lines[text_start:]
        ).strip()
        if not cue_text:
            continue
        out.append({"start": round(start, 3), "end": round(end, 3), "text": cue_text})
    return _dedupe(out)


def _parse_timed_xml(body: str) -> list[dict]:
    out: list[dict] = []
    for match in re.finditer(r"<text\b([^>]*)>(.*?)</text>", body, re.DOTALL | re.IGNORECASE):
        attrs, inner = match.group(1), match.group(2)
        start_m = re.search(r'start="([\d.]+)"', attrs)
        if not start_m:
            continue
        dur_m = re.search(r'dur="([\d.]+)"', attrs)
        start = float(start_m.group(1))
        dur = float(dur_m.group(1)) if dur_m else 0.0
        cue_text = _clean_text(inner)
        if cue_text:
            out.append(
                {"start": round(start, 3), "end": round(start + dur, 3), "text": cue_text}
            )
    if out:
        return _dedupe(out)

    for match in re.finditer(r"<p\b([^>]*)>(.*?)</p>", body, re.DOTALL | re.IGNORECASE):
        attrs, inner = match.group(1), match.group(2)
        begin_m = re.search(r'begin="([^"]+)"', attrs)
        end_m = re.search(r'end="([^"]+)"', attrs)
        if not begin_m or not end_m:
            continue
        start = _parse_clock(begin_m.group(1))
        end = _parse_clock(end_m.group(1))
        if start is None or end is None:
            continue
        cue_text = _clean_text(inner)
        if cue_text:
            out.append({"start": round(start, 3), "end": round(end, 3), "text": cue_text})
    return _dedupe(out)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _hms_to_seconds(hours: str, minutes: str, seconds: str, millis: str) -> float:
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(millis.ljust(3, "0")[:3]) / 1000.0
    )


def _parse_clock(value: str) -> float | None:
    value = value.strip()
    if value.endswith("s"):
        value = value[:-1]
    try:
        if ":" in value:
            parts = [float(p) for p in value.split(":")]
            while len(parts) < 3:
                parts.insert(0, 0.0)
            return parts[-3] * 3600 + parts[-2] * 60 + parts[-1]
        return float(value)
    except ValueError:
        return None


def _clean_text(value: str) -> str:
    return html.unescape(_TAG_RE.sub("", value)).replace("\n", " ").strip()


def _dedupe(segments: list[dict]) -> list[dict]:
    """Collapse consecutive segments with identical text (common in auto-subs)."""
    out: list[dict] = []
    for seg in segments:
        if out and out[-1]["text"] == seg["text"]:
            out[-1]["end"] = seg["end"]
            continue
        out.append(seg)
    return out
