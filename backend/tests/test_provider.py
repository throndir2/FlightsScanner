"""Unit tests for the deterministic mock flight provider."""

from __future__ import annotations

from datetime import date

from app.models.base import CabinClass
from app.services.provider import get_provider
from app.services.provider.base import ProviderQuery


def _query(*, nonstop: bool, cabin: CabinClass = CabinClass.ECONOMY) -> ProviderQuery:
    return ProviderQuery(
        origin="JFK",
        destination="LHR",
        departure_date=date(2026, 6, 1),
        return_date=date(2026, 6, 8),
        nonstop=nonstop,
        cabin_class=cabin,
    )


def test_mock_provider_is_deterministic() -> None:
    provider = get_provider("mock")
    q = _query(nonstop=False)
    first = provider.search_offers(q)
    second = provider.search_offers(q)
    assert [o.price for o in first] == [o.price for o in second]


def test_nonstop_query_returns_only_nonstop() -> None:
    provider = get_provider("mock")
    offers = provider.search_offers(_query(nonstop=True))
    assert offers
    assert all(o.stops == 0 and o.is_nonstop for o in offers)


def test_non_nonstop_query_includes_a_one_stop_option() -> None:
    provider = get_provider("mock")
    offers = provider.search_offers(_query(nonstop=False))
    assert any(o.stops == 1 for o in offers)


def test_premium_cabin_costs_more_than_economy() -> None:
    provider = get_provider("mock")
    eco = provider.search_offers(_query(nonstop=True, cabin=CabinClass.ECONOMY))[0]
    biz = provider.search_offers(_query(nonstop=True, cabin=CabinClass.BUSINESS))[0]
    assert biz.price > eco.price


def test_unknown_provider_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        get_provider("does-not-exist")
