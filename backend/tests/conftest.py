"""Shared fixtures for API integration tests.

Runs the **real** FastAPI app against an in-memory async SQLite database (no Postgres or
Redis required). The auth dependency is overridden to a fixed test user, and the Celery
enqueue is stubbed so requests never touch the broker.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

import app.models  # noqa: F401  -- registers all tables on SQLModel.metadata
from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.user import User


@pytest_asyncio.fixture
async def api(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[tuple[AsyncClient, UUID]]:
    """Yield an ``(AsyncClient, user_id)`` bound to a fresh in-memory database."""
    # Never enqueue to a real broker during API tests.
    monkeypatch.setattr("app.api.routes.alerts.enqueue_alert_refresh", lambda *a, **k: None)

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async with session_factory() as setup:
        user = User(email="test@example.com", display_name="Test")
        setup.add(user)
        await setup.commit()
        await setup.refresh(user)
        user_id = user.id

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_current_user() -> User:
        async with session_factory() as session:
            obj = await session.get(User, user_id)
            assert obj is not None
            return obj

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, user_id

    app.dependency_overrides.clear()
    await engine.dispose()
