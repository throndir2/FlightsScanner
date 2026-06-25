"""Unit tests for the Amadeus response parser (no network).

Validates ``parse_offers`` against representative Amadeus flight-offers payloads.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.base import CabinClass
from app.services.provider.amadeus import parse_offers
from app.services.provider.base import ProviderQuery


def _query() -> ProviderQuery:
    return ProviderQuery(
        origin="JFK",
        destination="LHR",
        departure_date=date(2026, 6, 1),
        return_date=date(2026, 6, 8),
        nonstop=False,
        cabin_class=CabinClass.ECONOMY,
        currency="USD",
    )


SAMPLE = {
    "data": [
        {
            "price": {"grandTotal": "412.50", "currency": "USD"},
            "validatingAirlineCodes": ["VS"],
            "itineraries": [
                {"segments": [{"carrierCode": "VS"}]},
                {"segments": [{"carrierCode": "VS"}, {"carrierCode": "DL"}]},
            ],
        },
        {
            "price": {"total": "300.00", "currency": "USD"},
            "itineraries": [{"segments": [{"carrierCode": "BA"}]}],
        },
    ],
    "dictionaries": {"carriers": {"VS": "VIRGIN ATLANTIC", "BA": "BRITISH AIRWAYS"}},
}


def test_parse_offers_basic() -> None:
    offers = parse_offers(SAMPLE, _query())
    assert len(offers) == 2

    first = offers[0]
    assert first.price == Decimal("412.50")
    assert first.currency == "USD"
    assert first.carrier == "VIRGIN ATLANTIC"  # resolved via dictionaries
    assert first.stops == 1  # max 2 segments across itineraries → 1 stop
    assert first.is_nonstop is False
    assert first.deep_link is None  # Self-Service API has no booking URL

    second = offers[1]
    assert second.price == Decimal("300.00")  # falls back to "total"
    assert second.stops == 0
    assert second.carrier == "BRITISH AIRWAYS"


def test_parse_offers_skips_unparseable_entries() -> None:
    payload = {
        "data": [
            {"price": {}},  # no total/grandTotal → skipped
            {
                "price": {"total": "100.00", "currency": "USD"},
                "itineraries": [{"segments": [{"carrierCode": "AA"}]}],
            },
        ]
    }
    offers = parse_offers(payload, _query())
    assert len(offers) == 1
    assert offers[0].price == Decimal("100.00")
    assert offers[0].carrier == "AA"  # no dictionaries → raw code retained


def test_parse_offers_empty_payload() -> None:
    assert parse_offers({}, _query()) == []
