"""FastAPI application factory.

Wires routers, CORS, the consistent error envelope, and a lifespan that disposes the async
engine on shutdown. See ``docs/architecture.md``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import alerts, auth, health
from app.core.config import settings
from app.core.errors import APIError, api_error_handler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup hooks could go here (warm caches, etc.).
    yield
    # Shutdown: release pooled DB connections cleanly.
    from app.core.database import async_engine

    await async_engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    app.add_exception_handler(APIError, api_error_handler)

    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health.router, prefix=settings.API_PREFIX)
    app.include_router(auth.router, prefix=settings.API_PREFIX)
    app.include_router(alerts.router, prefix=settings.API_PREFIX)
    return app


app = create_app()
