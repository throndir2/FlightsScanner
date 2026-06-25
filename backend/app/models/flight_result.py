"""``FlightResult`` table — a cached, priced itinerary for one concrete date pair.

The worker UPSERTs on ``(alert_id, departure_date, return_date, provider)`` so a refresh
overwrites the previous price for that pair instead of duplicating rows. See
``docs/database-schema.md`` and ``docs/caching-strategy.md``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Numeric, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import utcnow

if TYPE_CHECKING:  # avoid circular imports at runtime
    from app.models.flight_alert import FlightAlert


class FlightResult(SQLModel, table=True):
    __tablename__ = "flight_results"
    __table_args__ = (
        UniqueConstraint(
            "alert_id",
            "departure_date",
            "return_date",
            "provider",
            name="uq_flight_results_pair",
        ),
        Index("ix_flight_results_alert_price", "alert_id", "price"),
        Index("ix_flight_results_fetched_at", "fetched_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    alert_id: UUID = Field(
        foreign_key="flight_alerts.id",
        index=True,
        nullable=False,
        ondelete="CASCADE",
    )

    departure_date: date = Field(nullable=False)
    return_date: date = Field(nullable=False)

    price: Decimal = Field(sa_type=Numeric(10, 2), nullable=False)
    currency: str = Field(max_length=3, nullable=False)
    carrier: str | None = Field(default=None, max_length=64)
    stops: int = Field(default=0, ge=0, nullable=False)
    is_nonstop: bool = Field(default=False, nullable=False)
    deep_link: str | None = Field(default=None)
    provider: str = Field(max_length=32, nullable=False)

    fetched_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
    )

    alert: "FlightAlert" = Relationship(back_populates="results")
