"""Output storage for rendered MP4s.

Two backends, chosen at call time by :attr:`app.config.Settings.s3_enabled`:

* **S3-compatible** (prod): ``boto3`` ``put_object`` + a presigned GET URL.
* **Local media dir** (dev): copy under ``settings.MEDIA_ROOT`` and return a
  ``/media/<key>`` path that the API serves via a StaticFiles mount.

All failures surface as :class:`~app.exceptions.ExternalServiceError`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.config import settings
from app.exceptions import ExternalServiceError
from app.logging_config import get_logger

__all__ = ["store_output", "local_media_path", "ensure_media_root"]

logger = get_logger("services.storage")

# Presigned download links live for one week.
_PRESIGN_EXPIRY_SECONDS = 7 * 24 * 60 * 60
_MEDIA_URL_PREFIX = "/media/"


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).expanduser().resolve()


def ensure_media_root() -> Path:
    """Create ``settings.MEDIA_ROOT`` if needed and return it as an absolute path."""
    root = _media_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExternalServiceError(f"Cannot create media root {root}: {exc}") from exc
    return root


def _clean_key(key: str) -> str:
    cleaned = key.strip().replace("\\", "/").lstrip("/")
    if not cleaned or ".." in cleaned.split("/"):
        raise ExternalServiceError(f"Invalid storage key: {key!r}")
    return cleaned


def local_media_path(key: str) -> Path:
    """Resolve ``key`` to an absolute path under the media root (traversal-safe)."""
    root = ensure_media_root()
    target = (root / _clean_key(key)).resolve()
    if target != root and root not in target.parents:
        raise ExternalServiceError(f"Storage key escapes media root: {key!r}")
    return target


def _s3_client():
    try:
        import boto3  # imported lazily; only the worker/prod path needs it
    except ImportError as exc:  # pragma: no cover - prod image always has boto3
        raise ExternalServiceError("boto3 is not installed in this environment") from exc

    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
    )


def _store_s3(src: Path, key: str) -> str:
    client = _s3_client()
    try:
        with src.open("rb") as body:
            client.put_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=body,
                ContentType="video/mp4",
            )
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": key},
            ExpiresIn=_PRESIGN_EXPIRY_SECONDS,
        )
    except Exception as exc:
        logger.exception("S3 upload failed for key %s", key)
        raise ExternalServiceError(f"Failed to upload render output: {exc}") from exc
    logger.info("Stored render output in S3: s3://%s/%s", settings.S3_BUCKET, key)
    return url


def _store_local(src: Path, key: str) -> str:
    dest = local_media_path(key)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dest:
            shutil.copy2(src, dest)
    except OSError as exc:
        raise ExternalServiceError(f"Failed to store render output: {exc}") from exc
    logger.info("Stored render output locally: %s", dest)
    return f"{_MEDIA_URL_PREFIX}{key}"


def store_output(local_path: Path, key: str) -> str:
    """Persist ``local_path`` under ``key`` and return a retrievable URL.

    Returns a presigned ``https`` URL when S3 is configured, otherwise a
    ``/media/<key>`` path served by the API's StaticFiles mount.

    Raises:
        ExternalServiceError: If the source file is missing or the write fails.
    """
    src = Path(local_path)
    if not src.is_file():
        raise ExternalServiceError(f"Render output not found: {src}")

    key = _clean_key(key)
    if settings.s3_enabled:
        return _store_s3(src, key)
    return _store_local(src, key)
