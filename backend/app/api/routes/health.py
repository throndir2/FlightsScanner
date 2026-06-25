"""Health/liveness endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "flightsscanner-api",
        "version": settings.VERSION,
    }
