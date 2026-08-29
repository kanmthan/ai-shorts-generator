"""Centralised logging configuration.

Uses the stdlib :mod:`logging` module only - ``print`` is never used anywhere in
the codebase. Call :func:`configure_logging` once during application (and Celery
worker) startup.
"""

from __future__ import annotations

import logging
from logging.config import dictConfig

from app.config import settings

_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Configure root logging handlers and formatters.

    Idempotent: safe to call multiple times (only the first call applies).

    Args:
        level: Optional log-level override (e.g. ``"DEBUG"``). Defaults to
            ``settings.LOG_LEVEL``.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = (level or settings.LOG_LEVEL or "INFO").upper()

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": (
                        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
                    ),
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
            "loggers": {
                "uvicorn": {"level": log_level, "handlers": ["console"], "propagate": False},
                "uvicorn.error": {"level": log_level, "handlers": ["console"], "propagate": False},
                "uvicorn.access": {"level": log_level, "handlers": ["console"], "propagate": False},
                "celery": {"level": log_level, "handlers": ["console"], "propagate": False},
                "app": {"level": log_level, "handlers": ["console"], "propagate": False},
            },
        }
    )

    _CONFIGURED = True
    logging.getLogger("app").debug("Logging configured at level %s", log_level)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced application logger."""
    return logging.getLogger(f"app.{name}" if not name.startswith("app") else name)
