"""Application configuration.

All settings are sourced from environment variables (12-factor). See ``.env.example`` at
the repository root for the annotated list and ``docs/development.md`` for usage.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Meta ──────────────────────────────────────────────────────────────────
    PROJECT_NAME: str = "FlightsScanner"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    ENVIRONMENT: str = "development"

    # ── Database ──────────────────────────────────────────────────────────────
    # Async DSN (asyncpg) for the FastAPI request path.
    DATABASE_URL: str = "postgresql+asyncpg://flights:flights@localhost:5432/flights"
    # Sync DSN (psycopg2) for Celery workers and Alembic migrations.
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://flights:flights@localhost:5432/flights"
    DB_ECHO: bool = False

    # ── Redis (Celery broker + price cache) ───────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    ALGORITHM: str = "HS256"

    # Comma-separated allow-list of frontend origins for CORS (never "*").
    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # ── Caching / quota ───────────────────────────────────────────────────────
    CACHE_TTL_SECONDS: int = 14_400  # 4 hours
    PROVIDER_DAILY_QUOTA: int = 1_000
    # Upper bound on date pairs generated per alert refresh (defense-in-depth).
    MAX_DATE_PAIRS_PER_ALERT: int = 200

    # ── Flight provider ───────────────────────────────────────────────────────
    FLIGHT_PROVIDER: str = "mock"  # "mock" | "amadeus"
    AMADEUS_CLIENT_ID: str | None = None
    AMADEUS_CLIENT_SECRET: str | None = None
    AMADEUS_BASE_URL: str = "https://test.api.amadeus.com"

    # ── Background scheduling ──────────────────────────────────────────────────
    # How often Beat enqueues a sweep of all active alerts (seconds).
    REFRESH_INTERVAL_SECONDS: int = 60 * 30  # 30 minutes

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        """Accept a comma-separated string and normalize trailing slashes."""
        if isinstance(value, str) and not value.startswith("["):
            value = [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).rstrip("/") for origin in value]
        return value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton ``Settings`` instance."""
    return Settings()


settings = get_settings()
