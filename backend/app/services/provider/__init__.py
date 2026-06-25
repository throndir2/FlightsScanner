"""Flight provider abstraction.

A single :class:`FlightProvider` interface hides whichever external source supplies offers.
v1 ships a deterministic :class:`~app.services.provider.mock.MockFlightProvider` so the whole
system runs with zero external accounts. Real adapters (e.g. Amadeus) implement the same
protocol and are selected via the ``FLIGHT_PROVIDER`` setting.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.provider.base import (
    FlightOffer,
    FlightProvider,
    ProviderError,
    ProviderQuery,
)
from app.services.provider.mock import MockFlightProvider

__all__ = [
    "FlightOffer",
    "FlightProvider",
    "ProviderError",
    "ProviderQuery",
    "MockFlightProvider",
    "get_provider",
]


def get_provider(name: str | None = None) -> FlightProvider:
    """Return the configured provider implementation.

    Args:
        name: Override for ``settings.FLIGHT_PROVIDER`` (useful in tests).
    """
    provider_name = (name or settings.FLIGHT_PROVIDER).lower()

    if provider_name == "mock":
        return MockFlightProvider()
    if provider_name == "amadeus":
        # Imported lazily so mock-only deployments never import httpx.
        from app.services.provider.amadeus import AmadeusFlightProvider

        return AmadeusFlightProvider()
    raise ValueError(f"Unknown flight provider: {provider_name!r}")
