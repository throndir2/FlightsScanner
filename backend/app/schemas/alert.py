"""Alert DTOs: request validation for creation and the read/response shape.

These plain Pydantic models enforce the constraint rules from ``docs/api-spec.md`` before
anything is persisted, keeping the API contract decoupled from the SQLModel tables.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.base import CabinClass

_IATA_RE = re.compile(r"^[A-Z]{3}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def validate_alert_constraints(
    *,
    origin: str,
    destination: str,
    target_duration_days: int,
    duration_flexibility_days: int,
    earliest_departure_date: date,
    latest_departure_date: date | None,
    latest_return_date: date,
) -> None:
    """Validate the cross-field rules shared by create and update. Raises ``ValueError``."""
    if origin == destination:
        raise ValueError("origin and destination must differ")
    if duration_flexibility_days >= target_duration_days:
        raise ValueError("duration_flexibility_days must be smaller than target_duration_days")

    min_duration = target_duration_days - duration_flexibility_days
    if earliest_departure_date + timedelta(days=min_duration) > latest_return_date:
        raise ValueError("latest_return_date is earlier than the minimum trip allows")

    if latest_departure_date is not None:
        if latest_departure_date < earliest_departure_date:
            raise ValueError("latest_departure_date must be on or after earliest_departure_date")
        if latest_departure_date > latest_return_date:
            raise ValueError("latest_departure_date must be on or before latest_return_date")


class FlightAlertBase(BaseModel):
    """Shared, validated fields for an alert."""

    origin: str = Field(..., description="3-letter IATA code, e.g. JFK")
    destination: str = Field(..., description="3-letter IATA code, e.g. LHR")

    target_duration_days: int = Field(..., ge=1, le=365, description="Ideal trip length")
    duration_flexibility_days: int = Field(
        0, ge=0, le=30, description="± days around the target duration"
    )
    earliest_departure_date: date
    latest_departure_date: date | None = Field(
        None, description="Optional cap on the departure window; derived if omitted"
    )
    latest_return_date: date

    is_nonstop_required: bool = False
    max_stops: int | None = Field(None, ge=0, le=5)
    cabin_class: CabinClass = CabinClass.ECONOMY
    currency: str = Field("USD", description="ISO-4217 currency code")

    @field_validator("origin", "destination")
    @classmethod
    def _normalize_iata(cls, value: str) -> str:
        value = value.strip().upper()
        if not _IATA_RE.fullmatch(value):
            raise ValueError("must be a 3-letter IATA code")
        return value

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if not _CURRENCY_RE.fullmatch(value):
            raise ValueError("must be a 3-letter ISO-4217 currency code")
        return value

    @model_validator(mode="after")
    def _validate_constraints(self) -> "FlightAlertBase":
        validate_alert_constraints(
            origin=self.origin,
            destination=self.destination,
            target_duration_days=self.target_duration_days,
            duration_flexibility_days=self.duration_flexibility_days,
            earliest_departure_date=self.earliest_departure_date,
            latest_departure_date=self.latest_departure_date,
            latest_return_date=self.latest_return_date,
        )
        return self


class FlightAlertCreate(FlightAlertBase):
    """Request body for ``POST /api/alerts``.

    ``user_id`` is intentionally *not* accepted here — the owner is bound from the
    authenticated session to prevent mass-assignment (see ``docs/auth-and-security.md``).
    """


class FlightAlertUpdate(BaseModel):
    """Partial update for an alert (``PATCH``). All fields optional; only the provided ones
    change. Cross-field feasibility is re-validated against the merged record in the route.
    """

    origin: str | None = None
    destination: str | None = None
    target_duration_days: int | None = Field(None, ge=1, le=365)
    duration_flexibility_days: int | None = Field(None, ge=0, le=30)
    earliest_departure_date: date | None = None
    latest_departure_date: date | None = None
    latest_return_date: date | None = None
    is_nonstop_required: bool | None = None
    max_stops: int | None = Field(None, ge=0, le=5)
    cabin_class: CabinClass | None = None
    currency: str | None = None
    is_active: bool | None = None

    @field_validator("origin", "destination")
    @classmethod
    def _normalize_iata(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not _IATA_RE.fullmatch(value):
            raise ValueError("must be a 3-letter IATA code")
        return value

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not _CURRENCY_RE.fullmatch(value):
            raise ValueError("must be a 3-letter ISO-4217 currency code")
        return value


class FlightAlertRead(FlightAlertBase):
    """Response shape for an alert."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
