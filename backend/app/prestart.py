"""Startup bootstrap: wait for Postgres, then ensure the schema exists.

In v1 the schema is created with ``SQLModel.metadata.create_all`` so ``docker compose up``
works with zero manual steps. For **schema evolution** use Alembic migrations (see
``docs/database-schema.md``); in production, disable this create-all bootstrap and manage the
schema exclusively through ``alembic upgrade head``.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import text
from sqlmodel import SQLModel

import app.models  # noqa: F401  -- registers all tables on SQLModel.metadata
from app.core.database import sync_engine

logger = logging.getLogger("app.prestart")


def wait_for_db(*, max_attempts: int = 30, delay_seconds: float = 1.0) -> None:
    """Block until the database accepts a trivial query, or raise after retries."""
    for attempt in range(1, max_attempts + 1):
        try:
            with sync_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # connection refused while Postgres warms up
            logger.warning("DB not ready (attempt %d/%d): %s", attempt, max_attempts, exc)
            time.sleep(delay_seconds)
    raise RuntimeError("Database did not become ready in time")


def ensure_schema() -> None:
    SQLModel.metadata.create_all(sync_engine)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    wait_for_db()
    ensure_schema()
    logger.info("Database is ready and the schema is ensured.")


if __name__ == "__main__":
    main()
