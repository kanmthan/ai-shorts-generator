"""Stock B-roll asset lookup: Pexels (primary) -> Pixabay (fallback).

:func:`fetch_broll_asset` takes a plain dict describing one planned B-roll
segment and returns the fields to write back onto it
(``asset_url`` / ``asset_source`` / ``asset_status``).

* Tries each keyword in ``search_keywords`` order.
* Pexels first; Pixabay only if Pexels yields nothing.
* If neither provider key is configured -> ``asset_status="skipped"``.
* Results are cached in-process, keyed by ``sha1(keywords)``, so repeated
  segments within a run do not re-hit the APIs.
* Transient failures (HTTP 429 / 5xx) are retried with exponential backoff.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("services.broll")

__all__ = ["fetch_broll_asset", "clear_cache"]

_PEXELS_VIDEO_SEARCH = "https://api.pexels.com/videos/search"
_PIXABAY_VIDEO_SEARCH = "https://pixabay.com/api/videos/"

_HTTP_TIMEOUT = 15.0
_MAX_ATTEMPTS = 3
_BACKOFF_BASE = 0.5

# sha1(keywords) -> {"asset_url", "asset_source", "asset_status"}
_CACHE: dict[str, dict[str, Any]] = {}


def clear_cache() -> None:
    """Drop the in-process asset cache (used by tests / between projects)."""
    _CACHE.clear()


def _cache_key(keywords: list[str]) -> str:
    joined = "\x1f".join(k.strip().lower() for k in keywords if k and k.strip())
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def fetch_broll_asset(segment: dict[str, Any]) -> dict[str, Any]:
    """Resolve a stock asset for one B-roll ``segment`` dict.

    Args:
        segment: Must contain ``search_keywords`` (list[str]); ``use_broll`` is
            honoured when present.

    Returns:
        ``{"asset_url": str | None, "asset_source": str | None,
        "asset_status": "fetched" | "not_found" | "skipped"}``.
    """
    if segment.get("use_broll") is False:
        return {"asset_url": None, "asset_source": None, "asset_status": "skipped"}

    keywords = [
        str(k).strip()
        for k in (segment.get("search_keywords") or [])
        if k and str(k).strip()
    ]

    has_pexels = bool(settings.PEXELS_API_KEY)
    has_pixabay = bool(settings.PIXABAY_API_KEY)
    if not has_pexels and not has_pixabay:
        return {"asset_url": None, "asset_source": None, "asset_status": "skipped"}

    if not keywords:
        return {"asset_url": None, "asset_source": None, "asset_status": "not_found"}

    key = _cache_key(keywords)
    if key in _CACHE:
        return dict(_CACHE[key])

    result: dict[str, Any] = {
        "asset_url": None,
        "asset_source": None,
        "asset_status": "not_found",
    }

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            url = _search_pexels(client, keywords) if has_pexels else None
            if url:
                result = {
                    "asset_url": url,
                    "asset_source": "pexels",
                    "asset_status": "fetched",
                }
            elif has_pixabay:
                url = _search_pixabay(client, keywords)
                if url:
                    result = {
                        "asset_url": url,
                        "asset_source": "pixabay",
                        "asset_status": "fetched",
                    }
    except httpx.HTTPError as exc:  # network died mid-search - treat as not found
        logger.warning("B-roll lookup failed (%s); marking not_found", type(exc).__name__)

    _CACHE[key] = dict(result)
    return result


# --------------------------------------------------------------------------- #
# Provider calls                                                              #
# --------------------------------------------------------------------------- #
def _request_with_backoff(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response | None:
    """Issue a request, retrying on 429 / 5xx with exponential backoff."""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        response = client.request(method, url, **kwargs)
        if response.status_code < 400:
            return response
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == _MAX_ATTEMPTS:
                logger.warning(
                    "Stock provider %s returned %s; giving up",
                    url,
                    response.status_code,
                )
                return None
            time.sleep(_BACKOFF_BASE * (2 ** (attempt - 1)))
            continue
        # 4xx other than 429: not retryable
        logger.info("Stock provider %s returned %s", url, response.status_code)
        return None
    return None


def _search_pexels(client: httpx.Client, keywords: list[str]) -> str | None:
    """Return the first Pexels stock-video file URL for the first hit keyword."""
    headers = {"Authorization": settings.PEXELS_API_KEY}
    for keyword in keywords:
        response = _request_with_backoff(
            client,
            "GET",
            _PEXELS_VIDEO_SEARCH,
            headers=headers,
            params={"query": keyword, "per_page": 1, "orientation": "portrait"},
        )
        if response is None:
            continue
        videos = response.json().get("videos") or []
        if not videos:
            continue
        files = sorted(
            videos[0].get("video_files") or [],
            key=lambda f: f.get("width") or 0,
        )
        for f in files:
            if f.get("link"):
                return str(f["link"])
    return None


def _search_pixabay(client: httpx.Client, keywords: list[str]) -> str | None:
    """Return the first Pixabay stock-video URL for the first hit keyword."""
    for keyword in keywords:
        response = _request_with_backoff(
            client,
            "GET",
            _PIXABAY_VIDEO_SEARCH,
            params={
                "key": settings.PIXABAY_API_KEY,
                "q": keyword,
                "per_page": 3,
                "video_type": "film",
            },
        )
        if response is None:
            continue
        hits = response.json().get("hits") or []
        if not hits:
            continue
        variants = hits[0].get("videos") or {}
        for size in ("medium", "small", "large", "tiny"):
            candidate = variants.get(size) or {}
            if candidate.get("url"):
                return str(candidate["url"])
    return None
