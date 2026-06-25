"""Database engines and session factories.

FlightsScanner deliberately maintains **two** access paths against the same database:

* **Async** (``asyncpg``) for the FastAPI request path — non-blocking I/O under the event
  loop.
* **Sync** (``psycopg2``) for Celery workers and Alembic migrations — Celery's prefork
  model is synchronous, and embedding an event loop in a prefork worker is fragile.

This split is intentional and documented in
``docs/design.md`` → "A note on async (FastAPI) vs sync (Celery)".
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# ── Async (FastAPI) ───────────────────────────────────────────────────────────
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ── Sync (Celery / Alembic) ───────────────────────────────────────────────────
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    future=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)
