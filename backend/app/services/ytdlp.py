"""Shared yt-dlp option builder.

Centralises the auth workarounds YouTube now requires from datacenter IPs:
a browser-exported cookies file and/or an outbound proxy.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("services.ytdlp")

# yt-dlp rewrites `cookiefile` on exit, and its rewrite drops cookies it deems
# out of scope - which breaks a browser-exported YouTube session. So we always
# hand yt-dlp a private copy and leave the mounted original untouched.
_COOKIE_WORKDIR = os.path.join(tempfile.gettempdir(), "ytdlp-cookies")


def _writable_cookie_copy(src: str) -> str | None:
    try:
        os.makedirs(_COOKIE_WORKDIR, exist_ok=True)
        dst = os.path.join(_COOKIE_WORKDIR, "cookies.txt")
        shutil.copyfile(src, dst)
        return dst
    except OSError:
        logger.exception("Could not stage a writable cookie copy from %s", src)
        return None

_BASE: dict[str, Any] = {
    "skip_download": True,
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "socket_timeout": 30,
    "writesubtitles": False,
    "writeautomaticsub": False,
    "writethumbnail": False,
    # Return the info dict even when only storyboard "formats" are available
    # (metadata / caption probing never needs a real download URL).
    "ignore_no_formats_error": True,
    # Let yt-dlp fetch + cache its EJS solver script so it can crack YouTube's
    # nsig / "n challenge" (needed for real video formats in the render step).
    "remote_components": ["ejs:github"],
}


def build_ydl_opts(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return yt-dlp options with cookies / proxy applied when configured."""
    opts: dict[str, Any] = dict(_BASE)

    cookies = settings.YTDLP_COOKIES_FILE.strip()
    if cookies:
        if os.path.isfile(cookies):
            staged = _writable_cookie_copy(cookies)
            opts["cookiefile"] = staged or cookies
        else:
            logger.warning("YTDLP_COOKIES_FILE=%s not found; continuing without cookies", cookies)

    proxy = settings.YTDLP_PROXY.strip()
    if proxy:
        opts["proxy"] = proxy

    if extra:
        opts.update(extra)
    return opts


def cookies_configured() -> bool:
    c = settings.YTDLP_COOKIES_FILE.strip()
    return bool(c) and os.path.isfile(c)
