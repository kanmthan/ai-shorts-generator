"""Celery application instance.

Shared by the API (to enqueue) and the worker/beat processes (to execute).
Task modules land in ``app.tasks.*`` during Phase 2 and are picked up by
``autodiscover_tasks``.
"""

from __future__ import annotations

from celery import Celery

from app.config import settings
from app.logging_config import configure_logging

configure_logging()

celery_app = Celery(
    "ai_shorts_generator",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    # Task modules live at app.tasks.<name> (not app.tasks.<name>.tasks), so
    # autodiscover's default related_name would miss them — list them explicitly.
    include=[
        "app.tasks.ingest",
        "app.tasks.analyze",
        "app.tasks.render",
    ],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=60 * 60 * 24,  # 24h
)

celery_app.autodiscover_tasks(["app.tasks"])


@celery_app.task(name="app.tasks.ping")
def ping() -> str:
    """Trivial connectivity check task."""
    return "pong"
