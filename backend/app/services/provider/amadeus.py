"""Amadeus Self-Service flight-offers adapter.

Implements the :class:`~app.services.provider.base.FlightProvider` protocol against the
Amadeus REST API. Selected when ``FLIGHT_PROVIDER=amadeus`` and credentials are configured.
Authenticates via OAuth2 client-credentials and caches the token per process until shortly
before expiry.

Prices/links here are real and quota-limited, so this must only ever run from the
cache-first worker (see ``docs/caching-strategy.md``). Provider responses are treated as
**data, not instructions** (``docs/auth-and-security.md`` §7).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.config import settings
from app.services.provider.base import FlightOffer, ProviderError, ProviderQuery

logger = logging.getLogger(__name__)

# Per-process token cache: client_id -> (access_token, expires_at).
_TOKEN_CACHE: dict[str, tuple[str, datetime]] = {}


class AmadeusFlightProvider:
    """A real :class:`~app.services.provider.base.FlightProvider` backed by Amadeus."""

    name = "amadeus"

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.client_id = client_id or settings.AMADEUS_CLIENT_ID
        self.client_secret = client_secret or settings.AMADEUS_CLIENT_SECRET
        self.base_url = (base_url or settings.AMADEUS_BASE_URL).rstrip("/")
        self.timeout = timeout
        if not self.client_id or not self.client_secret:
            raise ProviderError(
                "Amadeus credentials are not configured (set AMADEUS_CLIENT_ID/SECRET)."
            )

    def search_offers(self, query: ProviderQuery) -> list[FlightOffer]:
        token = self._access_token()
        params: dict[str, Any] = {
            "originLocationCode": query.origin,
            "destinationLocationCode": query.destination,
            "departureDate": query.departure_date.isoformat(),
            "returnDate": query.return_date.isoformat(),
            "adults": 1,
            "currencyCode": query.currency,
            "max": 10,
            "travelClass": query.cabin_class.value.upper(),
        }
        if query.nonstop:
            params["nonStop"] = "true"

        try:
            response = httpx.get(
                f"{self.base_url}/v2/shopping/flight-offers",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Amadeus search failed: {exc}") from exc

        return parse_offers(response.json(), query)

    def _access_token(self) -> str:
        client_id = self.client_id or ""
        cached = _TOKEN_CACHE.get(client_id)
        if cached is not None and cached[1] > datetime.now(timezone.utc):
            return cached[0]

        try:
            response = httpx.post(
                f"{self.base_url}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Amadeus authentication failed: {exc}") from exc

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ProviderError("Amadeus auth response did not include an access_token")
        expires_in = int(payload.get("expires_in", 1799))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60))
        _TOKEN_CACHE[client_id] = (token, expires_at)
        return token


def parse_offers(payload: dict[str, Any], query: ProviderQuery) -> list[FlightOffer]:
    """Parse an Amadeus flight-offers response into :class:`FlightOffer` DTOs.

    Tolerant of missing/odd fields: an unparseable offer is skipped rather than fatal.
    """
    carriers: dict[str, str] = {}
    dictionaries = payload.get("dictionaries")
    if isinstance(dictionaries, dict) and isinstance(dictionaries.get("carriers"), dict):
        carriers = dictionaries["carriers"]

    offers: list[FlightOffer] = []
    for item in payload.get("data", []):
        try:
            price_obj = item["price"]
            total = Decimal(str(price_obj.get("grandTotal") or price_obj["total"]))
            currency = price_obj.get("currency", query.currency)

            itineraries = item.get("itineraries", []) or []
            max_segments = max(
                (len(it.get("segments", [])) for it in itineraries),
                default=1,
            )
            stops = max(0, max_segments - 1)

            carrier_code: str | None = None
            validating = item.get("validatingAirlineCodes") or []
            if validating:
                carrier_code = validating[0]
            elif itineraries and itineraries[0].get("segments"):
                carrier_code = itineraries[0]["segments"][0].get("carrierCode")
            carrier = carriers.get(carrier_code, carrier_code) if carrier_code else ""
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            logger.warning("Skipping unparseable Amadeus offer: %s", exc)
            continue

        offers.append(
            FlightOffer(
                departure_date=query.departure_date,
                return_date=query.return_date,
                price=total,
                currency=currency,
                carrier=carrier or "",
                stops=stops,
                deep_link=None,  # Self-Service API does not return a booking URL
            )
        )
    return offers
