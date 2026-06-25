"""Task dispatch helper.

Lets the API *enqueue* background work without importing task implementations. We send by
task **name** through the broker, so the API depends only on the lightweight Celery app
handle (which imports config only) — not on ``app.workers.tasks`` (which imports services,
providers, DB). This preserves the layering in ``docs/architecture.md``.
"""

from __future__ import annotations

from uuid import UUID

from app.workers.celery_app import celery_app

REFRESH_ALERT_TASK = "app.workers.tasks.refresh_alert"


def enqueue_alert_refresh(alert_id: UUID | str, *, force: bool = False) -> None:
    """Fire-and-forget: enqueue a refresh for a single alert.

    ``force=True`` bypasses the per-pair freshness cache check (but still respects the daily
    quota guard) — used by the manual "refresh now" endpoint.
    """
    celery_app.send_task(REFRESH_ALERT_TASK, args=[str(alert_id)], kwargs={"force": force})
