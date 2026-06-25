"""Deterministic mock flight provider.

Produces plausible, **stable** offers derived from the query so that:

* the same query always yields the same prices (good for caching and tests), and
* the system runs end-to-end with no external API account.

Prices are pseudo-random but seeded by the route and dates — they are *not* real fares.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

from app.services.provider.base import FlightOffer, ProviderQuery

# A small pool of fake marketing carriers.
_CARRIERS = ("VS", "BA", "AA", "DL", "UA", "LH", "AF", "KL")


class MockFlightProvider:
    """A stand-in :class:`~app.services.provider.base.FlightProvider`."""

    name = "mock"

    def search_offers(self, query: ProviderQuery) -> list[FlightOffer]:
        seed = self._seed(query)

        # Base economy price in [180, 779], stable per route+dates.
        base = 180 + (seed % 600)
        # Weekend departures cost a little more.
        if query.departure_date.weekday() >= 4:  # Fri/Sat/Sun-ish
            base = int(base * 1.08)
        # Cabin multiplier.
        base = int(base * _CABIN_MULTIPLIER.get(query.cabin_class.value, 1.0))

        carrier = _CARRIERS[seed % len(_CARRIERS)]

        offers: list[FlightOffer] = [
            self._offer(query, carrier=carrier, stops=0, price=Decimal(base)),
        ]

        # When non-stop is not required, also surface a cheaper one-stop option.
        if not query.nonstop:
            alt_carrier = _CARRIERS[(seed // 7) % len(_CARRIERS)]
            one_stop_price = Decimal(int(base * 0.82))
            offers.append(
                self._offer(query, carrier=alt_carrier, stops=1, price=one_stop_price)
            )

        return offers

    # ── helpers ────────────────────────────────────────────────────────────────
    @staticmethod
    def _seed(query: ProviderQuery) -> int:
        raw = (
            f"{query.origin}|{query.destination}|"
            f"{query.departure_date.isoformat()}|{query.return_date.isoformat()}"
        ).encode()
        return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")

    def _offer(
        self,
        query: ProviderQuery,
        *,
        carrier: str,
        stops: int,
        price: Decimal,
    ) -> FlightOffer:
        deep_link = (
            "https://book.example-air.com/search"
            f"?from={query.origin}&to={query.destination}"
            f"&depart={query.departure_date.isoformat()}"
            f"&return={query.return_date.isoformat()}"
            f"&carrier={carrier}&cabin={query.cabin_class.value}"
        )
        return FlightOffer(
            departure_date=query.departure_date,
            return_date=query.return_date,
            price=price,
            currency=query.currency,
            carrier=carrier,
            stops=stops,
            deep_link=deep_link,
        )


_CABIN_MULTIPLIER: dict[str, float] = {
    "economy": 1.0,
    "premium_economy": 1.6,
    "business": 3.2,
    "first": 5.0,
}
