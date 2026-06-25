"""Shared model building blocks: enums and the timestamp mixin."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, func
from sqlmodel import Field, SQLModel


class CabinClass(str, Enum):
    """Supported cabin classes for an itinerary search."""

    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


def utcnow() -> datetime:
    """Timezone-aware current UTC timestamp (used as a Python-side default)."""
    return datetime.now(timezone.utc)


class TimestampMixin(SQLModel):
    """Adds ``created_at`` / ``updated_at`` columns with DB + Python defaults."""

    created_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
        nullable=False,
    )
