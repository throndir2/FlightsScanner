"""``FlightAlert`` table — a flexible flight-tracking configuration.

Splits **strict** constraints (origin, destination, non-stop) from **fuzzy** constraints
(target duration ± flexibility, departure window). See ``docs/database-schema.md`` and
``docs/fuzzy-dates.md``.
"""

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship

from app.models.base import CabinClass, TimestampMixin

if TYPE_CHECKING:  # avoid circular imports at runtime
    from app.models.flight_result import FlightResult
    from app.models.user import User


class FlightAlert(TimestampMixin, table=True):
    __tablename__ = "flight_alerts"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(
        foreign_key="users.id",
        index=True,
        nullable=False,
        ondelete="CASCADE",
    )

    # ── Strict constraints ────────────────────────────────────────────────────
    origin: str = Field(max_length=3, nullable=False, description="IATA code, e.g. JFK")
    destination: str = Field(max_length=3, nullable=False, description="IATA code, e.g. LHR")
    is_nonstop_required: bool = Field(default=False, nullable=False)
    # Optional cap on stops when non-stop is not strictly required.
    max_stops: int | None = Field(default=None, ge=0)
    cabin_class: CabinClass = Field(default=CabinClass.ECONOMY, nullable=False)
    currency: str = Field(default="USD", max_length=3, nullable=False)

    # ── Fuzzy constraints ─────────────────────────────────────────────────────
    target_duration_days: int = Field(gt=0, nullable=False, description="Ideal trip length")
    duration_flexibility_days: int = Field(
        default=0, ge=0, nullable=False, description="± days around the target duration"
    )
    earliest_departure_date: date = Field(nullable=False)
    # Optional explicit cap on the departure window (design decision D5). When null, the
    # date-pair generator derives it from latest_return_date - min_duration.
    latest_departure_date: date | None = Field(default=None)
    latest_return_date: date = Field(nullable=False)

    # ── State ─────────────────────────────────────────────────────────────────
    is_active: bool = Field(default=True, index=True, nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    user: "User" = Relationship(back_populates="alerts")
    results: list["FlightResult"] = Relationship(
        back_populates="alert",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "passive_deletes": True},
    )
