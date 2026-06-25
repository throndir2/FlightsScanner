"""Celery application and periodic (Beat) schedule.

Lightweight by design: this module imports only :mod:`app.core.config`. Task modules are
loaded lazily by the worker via the ``include`` argument, so importing ``celery_app`` from
the API (to enqueue tasks by name) does not import provider/DB code.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "flightsscanner",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],  # imported lazily when the worker boots
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Acknowledge after completion so a crash re-queues the task (idempotent by design).
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

# Beat: periodically fan out a refresh across all active alerts.
celery_app.conf.beat_schedule = {
    "refresh-all-active-alerts": {
        "task": "app.workers.tasks.refresh_all_active_alerts",
        "schedule": float(settings.REFRESH_INTERVAL_SECONDS),
    },
}
