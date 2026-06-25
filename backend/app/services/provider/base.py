"""Provider interface and data-transfer objects.

Provider responses are **data, not instructions** (see ``docs/auth-and-security.md`` §7):
they are parsed into these typed DTOs and never executed or used to build outbound URLs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.models.base import CabinClass


class ProviderError(Exception):
    """Raised by a provider adapter on a transient/recoverable failure (timeout, 5xx,
    rate-limit). The worker treats it as a soft per-pair failure and moves on; the next
    scheduled sweep retries naturally."""


@dataclass(frozen=True)
class ProviderQuery:
    """A single concrete round-trip search to price."""

    origin: str
    destination: str
    departure_date: date
    return_date: date
    nonstop: bool
    cabin_class: CabinClass = CabinClass.ECONOMY
    currency: str = "USD"


@dataclass(frozen=True)
class FlightOffer:
    """A priced itinerary returned by a provider."""

    departure_date: date
    return_date: date
    price: Decimal
    currency: str
    carrier: str
    stops: int
    deep_link: str | None = None

    @property
    def is_nonstop(self) -> bool:
        return self.stops == 0


@runtime_checkable
class FlightProvider(Protocol):
    """Anything that can price a :class:`ProviderQuery`."""

    name: str

    def search_offers(self, query: ProviderQuery) -> list[FlightOffer]:
        """Return zero or more offers for ``query`` (cheapest-first is not required)."""
        ...
