"""Result DTOs: the read shapes returned by ``GET /api/alerts/{user_id}/results``."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FlightResultRead(BaseModel):
    """A single cached, priced itinerary for one date pair."""

    model_config = ConfigDict(from_attributes=True)

    departure_date: date
    return_date: date
    price: Decimal
    currency: str
    carrier: str | None = None
    stops: int
    is_nonstop: bool
    deep_link: str | None = None
    provider: str
    fetched_at: datetime


class AlertResults(BaseModel):
    """The cheapest cached results for a single alert.

    ``lowest_price`` and ``results`` are empty when no refresh has populated data yet.
    """

    alert_id: UUID
    origin: str
    destination: str
    is_nonstop_required: bool
    currency: str
    lowest_price: Decimal | None = None
    results: list[FlightResultRead] = []
