"""User service: get-or-create by email.

Reconciles the NextAuth identity with the backend ``users`` table (see
``docs/auth-and-security.md``). Async path (FastAPI).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.models.user import User


async def get_or_create_user(
    db: AsyncSession,
    *,
    email: str,
    display_name: str | None = None,
) -> User:
    """Return the user with ``email``, creating one if needed."""
    normalized = email.strip().lower()
    existing = (
        await db.execute(select(User).where(col(User.email) == normalized))
    ).scalars().first()
    if existing is not None:
        return existing

    user = User(email=normalized, display_name=display_name)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
