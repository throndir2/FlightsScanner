"""Shared FastAPI dependencies: database session and current-user resolution.

Auth model (see ``docs/auth-and-security.md``): the frontend forwards a backend-issued JWT
as a bearer token. In **development only**, an ``X-User-Id`` header is accepted as a
convenience so the API can be exercised without wiring the full NextAuth↔backend token
bridge. This fallback is impossible in production.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.errors import APIError
from app.core.security import decode_access_token
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async session, committing on success."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> User:
    """Resolve the authenticated user from a bearer token (or a dev ``X-User-Id``)."""
    user_id: UUID | None = None

    if credentials is not None:
        try:
            payload = decode_access_token(credentials.credentials)
            user_id = UUID(str(payload["sub"]))
        except Exception as exc:  # invalid signature, expiry, malformed sub, etc.
            raise APIError(401, "Invalid authentication token", "invalid_token") from exc
    elif not settings.is_production and x_user_id:
        try:
            user_id = UUID(x_user_id)
        except ValueError as exc:
            raise APIError(400, "Invalid X-User-Id header", "invalid_user_id") from exc

    if user_id is None:
        raise APIError(401, "Not authenticated", "unauthenticated")

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise APIError(401, "User not found or inactive", "unauthenticated")
    return user
