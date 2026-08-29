"""Shared yt-dlp option builder.

Centralises the auth workarounds YouTube now requires from datacenter IPs:
a browser-exported cookies file and/or an outbound proxy.
"""

from __future__ import annotations

import os
from typing import Any

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("services.ytdlp")

_BASE: dict[str, Any] = {
    "skip_download": True,
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "socket_timeout": 30,
    "writesubtitles": False,
    "writeautomaticsub": False,
    "writethumbnail": False,
}


def build_ydl_opts(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return yt-dlp options with cookies / proxy applied when configured."""
    opts: dict[str, Any] = dict(_BASE)

    cookies = settings.YTDLP_COOKIES_FILE.strip()
    if cookies:
        if os.path.isfile(cookies):
            opts["cookiefile"] = cookies
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
