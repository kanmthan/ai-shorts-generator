"""ffmpeg / yt-dlp rendering stages for the Shorts render pipeline.

Every function is a single pipeline stage. Each takes a working directory and
returns the :class:`~pathlib.Path` of the file it produced, so the Celery task
(:mod:`app.tasks.render`) can persist progress between stages.

Stage order (see PRP Module 4)::

    download_source_segment -> crop_vertical -> remove_silence
        -> overlay_broll -> burn_captions -> encode_final

All ffmpeg / subprocess failures are converted to
:class:`~app.exceptions.ExternalServiceError`. ``print`` is never used.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import ffmpeg

from app.config import settings
from app.exceptions import ExternalServiceError
from app.logging_config import get_logger

__all__ = [
    "download_source_segment",
    "crop_vertical",
    "remove_silence",
    "burn_captions",
    "overlay_broll",
    "encode_final",
]

logger = get_logger("services.rendering")

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
_DOWNLOAD_TIMEOUT_SECONDS = 30 * 60
_TRANSITION_FADE = ("fade", "dissolve")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _workdir(workdir: str | Path) -> Path:
    path = Path(workdir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ffprobe_binary() -> str:
    binary = settings.FFMPEG_BINARY
    if binary.endswith("ffmpeg"):
        return binary[: -len("ffmpeg")] + "ffprobe"
    return "ffprobe"


def _run(stream: Any, *, desc: str) -> None:
    """Execute an ffmpeg-python stream, mapping every failure to a domain error."""
    try:
        ffmpeg.run(
            stream,
            cmd=settings.FFMPEG_BINARY,
            overwrite_output=True,
            capture_stdout=True,
            capture_stderr=True,
        )
    except ffmpeg.Error as exc:  # non-zero exit
        stderr = (
            exc.stderr.decode("utf-8", "replace")
            if getattr(exc, "stderr", None)
            else str(exc)
        )
        logger.error("ffmpeg stage %r failed: %s", desc, stderr[-2000:])
        raise ExternalServiceError(f"ffmpeg {desc} stage failed") from exc
    except (OSError, ValueError) as exc:  # binary missing / bad args
        logger.exception("ffmpeg stage %r could not start", desc)
        raise ExternalServiceError(f"ffmpeg {desc} stage could not start: {exc}") from exc


def _probe_duration(path: str | Path) -> float:
    try:
        meta = ffmpeg.probe(str(path), cmd=_ffprobe_binary())
        return float(meta["format"]["duration"])
    except (ffmpeg.Error, KeyError, ValueError, OSError) as exc:
        logger.info("Could not probe duration for %s: %s", path, exc)
        return 0.0


def _parse_timecode(value: Any) -> float:
    """Parse ``HH:MM:SS`` / ``MM:SS`` / ``SS`` / numeric into float seconds."""
    if value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        parts = [float(p) for p in text.split(":")]
    except ValueError as exc:
        raise ExternalServiceError(f"Invalid timecode: {value!r}") from exc
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60.0 + part
    return seconds


def _seg_get(segment: Any, key: str, default: Any = None) -> Any:
    if isinstance(segment, dict):
        return segment.get(key, default)
    return getattr(segment, key, default)


def _escape_drawtext(text: str) -> str:
    out = text.replace("\\", r"\\\\")
    for ch in (":", "'", "%", "{", "}"):
        out = out.replace(ch, "\\" + ch)
    return out.replace("\n", " ")


def _resolve_asset(asset_url: str, workdir: Path) -> str | None:
    """Return an ffmpeg-usable input for a B-roll asset, or ``None`` if unusable."""
    if not asset_url:
        return None
    if asset_url.startswith(("http://", "https://")):
        return asset_url  # ffmpeg reads remote inputs directly
    if asset_url.startswith("/media/"):
        candidate = Path(settings.MEDIA_ROOT).expanduser() / asset_url[len("/media/") :]
    else:
        candidate = Path(asset_url)
    if candidate.is_file():
        return str(candidate)
    logger.warning("B-roll asset not found on disk: %s", asset_url)
    return None


# --------------------------------------------------------------------------- #
# stages
# --------------------------------------------------------------------------- #
def download_source_segment(
    url: str,
    start_hhmmss: str,
    end_hhmmss: str,
    workdir: str | Path,
) -> Path:
    """Download the source video with yt-dlp, then trim ``[start, end]`` with ffmpeg."""
    work = _workdir(workdir)
    start = _parse_timecode(start_hhmmss)
    end = _parse_timecode(end_hhmmss)
    if end <= start:
        raise ExternalServiceError(
            f"Render window end ({end_hhmmss}) must be after start ({start_hhmmss})"
        )

    source = work / "source_full.mp4"
    ytdlp = shutil.which(settings.YTDLP_BINARY) or settings.YTDLP_BINARY
    cmd = [
        ytdlp,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--force-overwrites",
        "-f",
        "bv*+ba/b",
        "--merge-output-format",
        "mp4",
        "-o",
        str(source),
        url,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_DOWNLOAD_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.exception("yt-dlp could not start for %s", url)
        raise ExternalServiceError(f"yt-dlp could not start: {exc}") from exc

    if proc.returncode != 0 or not source.is_file():
        logger.error("yt-dlp failed (%s): %s", proc.returncode, (proc.stderr or "")[-2000:])
        raise ExternalServiceError("yt-dlp failed to download the source video")

    trimmed = work / "segment.mp4"
    stream = ffmpeg.input(str(source), ss=start, to=end)
    stream = ffmpeg.output(
        stream,
        str(trimmed),
        vcodec="libx264",
        acodec="aac",
        pix_fmt="yuv420p",
        avoid_negative_ts="make_zero",
    )
    _run(stream, desc="download/trim")
    return trimmed


def crop_vertical(src: str | Path, workdir: str | Path) -> Path:
    """Scale + centre-crop to 1080x1920 (9:16)."""
    work = _workdir(workdir)
    out = work / "vertical.mp4"
    inp = ffmpeg.input(str(src))
    video = (
        inp.video.filter(
            "scale",
            TARGET_WIDTH,
            TARGET_HEIGHT,
            force_original_aspect_ratio="increase",
        )
        .filter("crop", TARGET_WIDTH, TARGET_HEIGHT)
        .filter("setsar", "1")
    )
    stream = ffmpeg.output(
        video,
        inp.audio,
        str(out),
        vcodec="libx264",
        acodec="aac",
        pix_fmt="yuv420p",
        **{"aspect": "9:16"},
    )
    _run(stream, desc="crop")
    return out


def remove_silence(src: str | Path, workdir: str | Path) -> Path:
    """Trim long silences from the audio track while keeping the original audio."""
    work = _workdir(workdir)
    out = work / "desilenced.mp4"
    inp = ffmpeg.input(str(src))
    audio = inp.audio.filter(
        "silenceremove",
        start_periods=1,
        start_duration=0.3,
        start_threshold="-40dB",
        stop_periods=-1,
        stop_duration=1.0,
        stop_threshold="-40dB",
    )
    stream = ffmpeg.output(
        inp.video,
        audio,
        str(out),
        vcodec="copy",
        acodec="aac",
    )
    _run(stream, desc="remove-silence")
    return out


def burn_captions(
    src: str | Path,
    subtitle_segments: list[Any] | None,
    workdir: str | Path,
) -> Path:
    """Burn word-timed captions in; highlighted segments are drawn larger/coloured."""
    work = _workdir(workdir)
    segments = list(subtitle_segments or [])
    if not segments:
        logger.info("burn_captions: no subtitle segments, passing clip through")
        return Path(src)

    inp = ffmpeg.input(str(src))
    video = inp.video
    drawn = 0
    for seg in segments:
        text = (_seg_get(seg, "text") or "").strip()
        if not text:
            continue
        start = _parse_timecode(_seg_get(seg, "start"))
        end = _parse_timecode(_seg_get(seg, "end"))
        if end <= start:
            continue
        emphasised = bool(_seg_get(seg, "highlight_words"))
        video = video.filter(
            "drawtext",
            text=_escape_drawtext(text),
            fontcolor="#FFD400" if emphasised else "white",
            fontsize=68 if emphasised else 52,
            borderw=4,
            bordercolor="black",
            box=1,
            boxcolor="black@0.45",
            boxborderw=16,
            x="(w-text_w)/2",
            y="h-text_h-180",
            enable=f"between(t,{start:.3f},{end:.3f})",
        )
        drawn += 1

    if drawn == 0:
        logger.info("burn_captions: no usable subtitle segments, passing clip through")
        return Path(src)

    out = work / "captioned.mp4"
    stream = ffmpeg.output(
        video,
        inp.audio,
        str(out),
        vcodec="libx264",
        acodec="aac",
        pix_fmt="yuv420p",
    )
    _run(stream, desc="captions")
    return out


def overlay_broll(
    src: str | Path,
    broll_segments: list[Any] | None,
    workdir: str | Path,
) -> Path:
    """Overlay each ``asset_status == "fetched"`` B-roll clip over its own window.

    Segments without a fetched asset are skipped. An overlay is never allowed to
    span the whole clip - it is clamped away from the clip's edges.
    """
    work = _workdir(workdir)
    usable = [
        seg
        for seg in (broll_segments or [])
        if _seg_get(seg, "asset_status") == "fetched" and _seg_get(seg, "asset_url")
    ]
    if not usable:
        logger.info("overlay_broll: no fetched B-roll assets, passing clip through")
        return Path(src)

    base_duration = _probe_duration(src)
    inp = ffmpeg.input(str(src))
    video = inp.video
    applied = 0
    for seg in usable:
        start = _parse_timecode(_seg_get(seg, "start"))
        end = _parse_timecode(_seg_get(seg, "end"))
        if end <= start:
            continue
        if base_duration:
            # never let a single overlay cover the entire clip
            edge = max(1.0, base_duration * 0.1)
            if start <= edge and end >= base_duration - edge:
                end = min(end, base_duration - edge)
            if end <= start:
                continue

        asset_input = _resolve_asset(_seg_get(seg, "asset_url"), work)
        if asset_input is None:
            continue

        transition = _seg_get(seg, "transition") or "smooth_cut"
        overlay = (
            ffmpeg.input(asset_input)
            .video.filter(
                "scale",
                TARGET_WIDTH,
                TARGET_HEIGHT,
                force_original_aspect_ratio="increase",
            )
            .filter("crop", TARGET_WIDTH, TARGET_HEIGHT)
            .filter("setpts", "PTS-STARTPTS")
        )
        if transition in _TRANSITION_FADE:
            span = max(0.1, end - start)
            overlay = overlay.filter("fade", type="in", st=0, d=min(0.4, span / 2)).filter(
                "fade", type="out", st=max(0.0, span - 0.4), d=min(0.4, span / 2)
            )
        video = ffmpeg.overlay(
            video,
            overlay,
            enable=f"between(t,{start:.3f},{end:.3f})",
        )
        applied += 1

    if applied == 0:
        logger.info("overlay_broll: no B-roll segments applied, passing clip through")
        return Path(src)

    out = work / "broll.mp4"
    stream = ffmpeg.output(
        video,
        inp.audio,
        str(out),
        vcodec="libx264",
        acodec="aac",
        pix_fmt="yuv420p",
    )
    _run(stream, desc="broll")
    return out


def encode_final(src: str | Path, workdir: str | Path) -> Path:
    """Final H.264/AAC MP4 encode, enforcing ``settings.MAX_OUTPUT_FILE_MB``."""
    work = _workdir(workdir)
    out = work / "final.mp4"
    max_bytes = settings.MAX_OUTPUT_FILE_MB * 1024 * 1024

    def _encode(target: Path, *, video_bitrate: str, audio_bitrate: str) -> None:
        stream = ffmpeg.output(
            ffmpeg.input(str(src)),
            str(target),
            vcodec="libx264",
            acodec="aac",
            video_bitrate=video_bitrate,
            audio_bitrate=audio_bitrate,
            pix_fmt="yuv420p",
            preset="medium",
            movflags="+faststart",
            format="mp4",
        )
        _run(stream, desc="encode")

    _encode(out, video_bitrate="6M", audio_bitrate="192k")
    size = out.stat().st_size if out.is_file() else 0
    if size == 0:
        raise ExternalServiceError("Final encode produced an empty file")

    if size > max_bytes:
        logger.warning(
            "Output %d bytes exceeds %d MB cap; re-encoding at a lower bitrate",
            size,
            settings.MAX_OUTPUT_FILE_MB,
        )
        capped = work / "final_capped.mp4"
        _encode(capped, video_bitrate="3M", audio_bitrate="128k")
        capped_size = capped.stat().st_size if capped.is_file() else 0
        if capped_size == 0 or capped_size > max_bytes:
            raise ExternalServiceError(
                f"Rendered output exceeds the {settings.MAX_OUTPUT_FILE_MB} MB limit"
            )
        return capped

    return out
