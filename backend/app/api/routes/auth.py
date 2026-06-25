"""Auth endpoints.

v1 ships a **development-only** token mint so the API (and the frontend's NextAuth
Credentials provider) can obtain a backend JWT without a full identity provider. In
production this endpoint is disabled; wire a real OAuth/credentials flow with password
verification instead. See ``docs/auth-and-security.md``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.errors import APIError
from app.core.security import create_access_token
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


class DevLoginRequest(BaseModel):
    email: str
    display_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID


@router.post("/dev-login", response_model=TokenResponse)
async def dev_login(
    payload: DevLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Get-or-create a user by email and return a backend JWT (development only)."""
    if settings.is_production:
        raise APIError(403, "dev-login is disabled in production", "forbidden")

    user = await user_service.get_or_create_user(
        db, email=payload.email, display_name=payload.display_name
    )
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, user_id=user.id)
