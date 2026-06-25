"""Celery worker package.

``celery_app`` holds the Celery instance and the Beat schedule; ``tasks`` holds the
cache-first refresh logic. ``celery_app`` imports **only** config so that the API can import
it (to enqueue by name) without pulling in task implementations.
"""

from app.workers.celery_app import celery_app

__all__ = ["celery_app"]
