"""Unit tests for the cache-first decision logic in ``app.workers.tasks``.

The Redis cache and the DB session are mocked, so these tests run with no external services
and assert the *control flow* described in ``docs/caching-strategy.md`` (when the provider is
and is not called).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.base import CabinClass
from app.services.provider.base import FlightOffer, ProviderError, ProviderQuery
from app.workers import tasks


class FakeProvider:
    name = "mock"

    def __init__(self, offers: list[FlightOffer] | None = None, error: Exception | None = None):
        self._offers = offers or []
        self._error = error
        self.called = False

    def search_offers(self, query: ProviderQuery) -> list[FlightOffer]:
        self.called = True
        if self._error is not None:
            raise self._error
        return self._offers


@pytest.fixture
def query() -> ProviderQuery:
    return ProviderQuery(
        origin="JFK",
        destination="LHR",
        departure_date=date(2026, 6, 1),
        return_date=date(2026, 6, 8),
        nonstop=False,
        cabin_class=CabinClass.ECONOMY,
        currency="USD",
    )


def _offer(price: int, stops: int = 0) -> FlightOffer:
    return FlightOffer(
        departure_date=date(2026, 6, 1),
        return_date=date(2026, 6, 8),
        price=Decimal(price),
        currency="USD",
        carrier="VS",
        stops=stops,
        deep_link="https://book.example-air.com/x",
    )


def _patch_cache(monkeypatch, *, cached=None, lock=True, quota=True, sink: dict | None = None):
    sink = sink if sink is not None else {}

    def _release(_key: str) -> None:
        sink["released"] = True

    monkeypatch.setattr(tasks.cache, "get_cached_price", lambda key: cached)
    monkeypatch.setattr(tasks.cache, "acquire_fetch_lock", lambda key: lock)
    monkeypatch.setattr(tasks.cache, "release_fetch_lock", _release)
    monkeypatch.setattr(tasks.cache, "try_consume_quota", lambda name: quota)
    monkeypatch.setattr(
        tasks.cache, "cache_price", lambda key, offer: sink.update({"key": key, "offer": offer})
    )
    return sink


def test_cache_hit_skips_provider(monkeypatch, query) -> None:
    _patch_cache(monkeypatch, cached={"price": "100"})
    provider = FakeProvider(offers=[_offer(100)])
    db = MagicMock()

    assert tasks._refresh_one_pair(db, uuid4(), provider, query) == "cache_hit"
    assert provider.called is False
    db.execute.assert_not_called()


def test_cache_miss_fetches_caches_and_picks_cheapest(monkeypatch, query) -> None:
    sink = _patch_cache(monkeypatch, cached=None)
    provider = FakeProvider(offers=[_offer(200, stops=0), _offer(150, stops=1)])
    db = MagicMock()

    assert tasks._refresh_one_pair(db, uuid4(), provider, query) == "fetched"
    assert provider.called is True
    db.execute.assert_called_once()                 # UPSERT issued
    assert sink["offer"].price == Decimal(150)      # cheapest selected and cached
    assert sink.get("released") is True             # lock always released


def test_lock_contention_skips(monkeypatch, query) -> None:
    _patch_cache(monkeypatch, cached=None, lock=False)
    provider = FakeProvider(offers=[_offer(100)])
    db = MagicMock()

    assert tasks._refresh_one_pair(db, uuid4(), provider, query) == "skipped_locked"
    assert provider.called is False
    db.execute.assert_not_called()


def test_quota_exhausted_defers(monkeypatch, query) -> None:
    _patch_cache(monkeypatch, cached=None, quota=False)
    provider = FakeProvider(offers=[_offer(100)])
    db = MagicMock()

    assert tasks._refresh_one_pair(db, uuid4(), provider, query) == "quota_exceeded"
    assert provider.called is False
    db.execute.assert_not_called()


def test_provider_error_is_soft(monkeypatch, query) -> None:
    _patch_cache(monkeypatch, cached=None)
    provider = FakeProvider(error=ProviderError("boom"))
    db = MagicMock()

    assert tasks._refresh_one_pair(db, uuid4(), provider, query) == "error"
    db.execute.assert_not_called()


def test_no_offers(monkeypatch, query) -> None:
    _patch_cache(monkeypatch, cached=None)
    provider = FakeProvider(offers=[])
    db = MagicMock()

    assert tasks._refresh_one_pair(db, uuid4(), provider, query) == "no_offers"
    db.execute.assert_not_called()
