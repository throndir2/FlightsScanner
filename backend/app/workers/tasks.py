"""Celery tasks: the cache-first refresh pipeline.

This is the heart of the cost-control strategy. ``refresh_alert`` expands an alert into
date pairs and, **per pair**, only calls the provider on a genuine cache miss — guarded by
a TTL cache, a daily quota counter, and a short in-flight lock. See
``docs/caching-strategy.md`` for the full model.

Runs synchronously (``psycopg2`` session, sync ``redis-py``) because Celery prefork workers
are synchronous.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col

from app.core.config import settings
from app.core.database import SyncSessionLocal
from app.models.flight_alert import FlightAlert
from app.models.flight_result import FlightResult
from app.services import cache
from app.services.provider import FlightProvider, ProviderError, ProviderQuery, get_provider
from app.utils.date_logic import generate_date_pairs
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Outcome labels for a single date-pair refresh (used for the run summary).
_OUTCOMES = ("cache_hit", "fetched", "skipped_locked", "quota_exceeded", "no_offers", "error")


@celery_app.task(name="app.workers.tasks.refresh_alert", bind=True)
def refresh_alert(self, alert_id: str, force: bool = False) -> dict:
    """Refresh cached prices for every date pair of a single alert (cache-first).

    ``force=True`` skips the per-pair freshness check (manual refresh) but still honors the
    quota guard and in-flight lock.
    """
    summary = {label: 0 for label in _OUTCOMES}

    with SyncSessionLocal() as db:
        alert = db.get(FlightAlert, UUID(alert_id))
        if alert is None:
            logger.warning("refresh_alert: alert %s not found", alert_id)
            return {"alert_id": alert_id, "status": "not_found"}
        if not alert.is_active:
            return {"alert_id": alert_id, "status": "inactive"}

        provider = get_provider()
        pairs = generate_date_pairs(alert, max_pairs=settings.MAX_DATE_PAIRS_PER_ALERT)

        for pair in pairs:
            query = ProviderQuery(
                origin=alert.origin,
                destination=alert.destination,
                departure_date=pair.departure_date,
                return_date=pair.return_date,
                nonstop=alert.is_nonstop_required,
                cabin_class=alert.cabin_class,
                currency=alert.currency,
            )
            outcome = _refresh_one_pair(db, alert.id, provider, query, force=force)
            summary[outcome] += 1
            if outcome == "fetched":
                # Commit per fetch so progress survives a later failure and shows up to the
                # API immediately.
                db.commit()

    result = {
        "alert_id": alert_id,
        "provider": provider.name,
        "pairs": len(pairs),
        **summary,
    }
    logger.info("refresh_alert %s -> %s", alert_id, result)
    return result


@celery_app.task(name="app.workers.tasks.refresh_all_active_alerts")
def refresh_all_active_alerts() -> dict:
    """Beat entry point: enqueue a ``refresh_alert`` for every active alert."""
    with SyncSessionLocal() as db:
        alert_ids = (
            db.execute(select(col(FlightAlert.id)).where(col(FlightAlert.is_active).is_(True)))
            .scalars()
            .all()
        )

    for alert_id in alert_ids:
        refresh_alert.delay(str(alert_id))

    logger.info("Enqueued refresh for %d active alert(s)", len(alert_ids))
    return {"enqueued": len(alert_ids)}


# ── internals ──────────────────────────────────────────────────────────────────
def _refresh_one_pair(
    db,
    alert_id: UUID,
    provider: FlightProvider,
    query: ProviderQuery,
    *,
    force: bool = False,
) -> str:
    """Refresh a single date pair. Returns one of :data:`_OUTCOMES`.

    Order matters: cheap checks first, then lock → re-check → quota → provider call. When
    ``force`` is set, the freshness checks are skipped (but quota and locking still apply).
    """
    key = cache.build_price_key(query)

    # 1. Cheap cache check — the dominant path once warm (skipped when forced).
    if not force and cache.get_cached_price(key) is not None:
        return "cache_hit"

    # 2. Single-flight: only one worker fetches a given key at a time.
    if not cache.acquire_fetch_lock(key):
        return "skipped_locked"

    try:
        # 3. Re-check inside the lock (another worker may have just populated it).
        if not force and cache.get_cached_price(key) is not None:
            return "cache_hit"

        # 4. Quota guard — never exceed the provider's daily free-tier budget.
        if not cache.try_consume_quota(provider.name):
            logger.warning("Quota exhausted (provider=%s); deferring %s", provider.name, key)
            return "quota_exceeded"

        # 5. Cache miss → the one place we actually call the provider.
        try:
            offers = provider.search_offers(query)
        except ProviderError as exc:
            logger.warning("Provider error for %s: %s", key, exc)
            return "error"

        if not offers:
            return "no_offers"

        cheapest = min(offers, key=lambda offer: offer.price)
        _upsert_result(db, alert_id, provider.name, cheapest)
        cache.cache_price(key, cheapest)
        return "fetched"
    finally:
        cache.release_fetch_lock(key)


def _upsert_result(db, alert_id: UUID, provider_name: str, offer) -> None:
    """UPSERT a FlightResult on ``(alert_id, departure, return, provider)``.

    Uses Postgres ``ON CONFLICT`` so a refresh overwrites the prior price for the pair
    instead of inserting a duplicate. ``id`` is supplied explicitly because the core insert
    bypasses SQLModel's Python-side default.
    """
    now = datetime.now(timezone.utc)
    stmt = pg_insert(FlightResult).values(
        id=uuid4(),
        alert_id=alert_id,
        departure_date=offer.departure_date,
        return_date=offer.return_date,
        price=offer.price,
        currency=offer.currency,
        carrier=offer.carrier,
        stops=offer.stops,
        is_nonstop=offer.is_nonstop,
        deep_link=offer.deep_link,
        provider=provider_name,
        fetched_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_flight_results_pair",
        set_={
            "price": stmt.excluded.price,
            "currency": stmt.excluded.currency,
            "carrier": stmt.excluded.carrier,
            "stops": stmt.excluded.stops,
            "is_nonstop": stmt.excluded.is_nonstop,
            "deep_link": stmt.excluded.deep_link,
            "fetched_at": stmt.excluded.fetched_at,
        },
    )
    db.execute(stmt)
