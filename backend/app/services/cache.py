"""Redis cache helpers: price cache keys, TTL get/set, daily quota guard, and in-flight
locks.

These run **synchronously** because the Celery worker (their primary caller) is sync. An
async client getter is provided for the API's health check. See
``docs/caching-strategy.md`` for the key schema and TTL rationale.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import redis
import redis.asyncio as aioredis

from app.core.config import settings
from app.services.provider.base import FlightOffer, ProviderQuery

# Module-level singletons (lazily created).
_sync_client: redis.Redis | None = None
_async_client: aioredis.Redis | None = None

_ONE_DAY_SECONDS = 60 * 60 * 24


def get_sync_redis() -> redis.Redis:
    """Return a process-wide sync Redis client (decoded strings)."""
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _sync_client


def get_async_redis() -> aioredis.Redis:
    """Return a process-wide async Redis client (decoded strings)."""
    global _async_client
    if _async_client is None:
        _async_client = aioredis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _async_client


# ── Price cache ────────────────────────────────────────────────────────────────
def build_price_key(query: ProviderQuery) -> str:
    """Canonical, lowercased cache key for a query.

    Excludes alert/user ids so identical queries from different alerts share one entry
    (global dedupe). See ``docs/caching-strategy.md`` §2.
    """
    nonstop = "1" if query.nonstop else "0"
    return (
        f"price:{query.origin.lower()}:{query.destination.lower()}:"
        f"{query.departure_date.isoformat()}:{query.return_date.isoformat()}:"
        f"{nonstop}:{query.cabin_class.value}"
    )


def get_cached_price(key: str) -> dict[str, Any] | None:
    """Return the cached payload for ``key`` or ``None`` on miss."""
    raw = get_sync_redis().get(key)
    if raw is None:
        return None
    return json.loads(raw)


def cache_price(key: str, offer: FlightOffer, *, ttl: int | None = None) -> None:
    """Store the lowest offer for a date pair with a TTL (default 4h)."""
    payload = {
        "price": str(offer.price),
        "currency": offer.currency,
        "carrier": offer.carrier,
        "stops": offer.stops,
        "is_nonstop": offer.is_nonstop,
        "deep_link": offer.deep_link,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    get_sync_redis().setex(key, ttl or settings.CACHE_TTL_SECONDS, json.dumps(payload))


# ── Daily provider quota guard ───────────────────────────────────────────────
def _quota_key(provider: str) -> str:
    day = datetime.now(UTC).strftime("%Y%m%d")
    return f"quota:{provider}:{day}"


def try_consume_quota(provider: str, *, limit: int | None = None) -> bool:
    """Best-effort: atomically reserve one provider call for today.

    Returns ``True`` if within budget (and consumes one unit), ``False`` if the daily
    quota is exhausted. The counter expires at the next UTC day.
    """
    limit = settings.PROVIDER_DAILY_QUOTA if limit is None else limit
    client = get_sync_redis()
    key = _quota_key(provider)

    count = client.incr(key)
    if count == 1:
        client.expire(key, _ONE_DAY_SECONDS)
    if count > limit:
        # Undo the over-budget increment so the counter settles at the cap.
        client.decr(key)
        return False
    return True


# ── In-flight lock (thundering-herd guard) ───────────────────────────────────
def acquire_fetch_lock(price_key: str, *, ttl: int = 60) -> bool:
    """Try to acquire a short lock for a price key. ``True`` if acquired."""
    return bool(get_sync_redis().set(f"lock:{price_key}", "1", nx=True, ex=ttl))


def release_fetch_lock(price_key: str) -> None:
    get_sync_redis().delete(f"lock:{price_key}")
