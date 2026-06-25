"""Alert service: create alerts and query the cheapest cached results for a user.

Runs on the **async** path (FastAPI). Reads never touch a provider — only Postgres (and,
implicitly, whatever the worker has already cached). See ``docs/api-spec.md``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.core.config import settings
from app.models.flight_alert import FlightAlert
from app.models.flight_result import FlightResult
from app.schemas.alert import FlightAlertCreate
from app.schemas.result import AlertResults, FlightResultRead


async def create_alert(
    db: AsyncSession,
    *,
    user_id: UUID,
    payload: FlightAlertCreate,
) -> FlightAlert:
    """Persist a new alert owned by ``user_id``.

    The owner is bound from the authenticated session — any ``user_id`` in the body is
    ignored by construction (the create schema has no such field).
    """
    alert = FlightAlert(user_id=user_id, **payload.model_dump())
    db.add(alert)
    await db.flush()
    await db.refresh(alert)
    return alert


async def list_alerts(db: AsyncSession, *, user_id: UUID) -> list[FlightAlert]:
    """Return all alerts owned by ``user_id``, newest first."""
    stmt = (
        select(FlightAlert)
        .where(col(FlightAlert.user_id) == user_id)
        .order_by(col(FlightAlert.created_at).desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_owned_alert(
    db: AsyncSession,
    *,
    user_id: UUID,
    alert_id: UUID,
) -> FlightAlert | None:
    """Return the alert if it exists and is owned by ``user_id``, else ``None``.

    Treating "not found" and "not owned" identically avoids leaking existence.
    """
    alert = await db.get(FlightAlert, alert_id)
    if alert is None or alert.user_id != user_id:
        return None
    return alert


async def apply_alert_update(
    db: AsyncSession,
    *,
    alert: FlightAlert,
    data: dict[str, Any],
) -> FlightAlert:
    """Apply a validated partial-update dict to ``alert`` and persist it."""
    for key, value in data.items():
        setattr(alert, key, value)
    await db.flush()
    await db.refresh(alert)
    return alert


async def delete_alert(db: AsyncSession, *, alert: FlightAlert) -> None:
    """Delete an alert (cascades to its results)."""
    await db.delete(alert)
    await db.flush()



async def get_results_for_user(
    db: AsyncSession,
    *,
    user_id: UUID,
    top_n: int = 1,
    include_stale: bool = True,
    alert_id: UUID | None = None,
) -> list[AlertResults]:
    """Return the cheapest cached results per active alert for ``user_id``."""
    stmt = select(FlightAlert).where(
        col(FlightAlert.user_id) == user_id,
        col(FlightAlert.is_active).is_(True),
    )
    if alert_id is not None:
        stmt = stmt.where(col(FlightAlert.id) == alert_id)

    alerts = (await db.execute(stmt)).scalars().all()

    out: list[AlertResults] = []
    for alert in alerts:
        results_stmt = select(FlightResult).where(col(FlightResult.alert_id) == alert.id)
        if not include_stale:
            cutoff = datetime.now(UTC) - timedelta(seconds=settings.CACHE_TTL_SECONDS)
            results_stmt = results_stmt.where(col(FlightResult.fetched_at) >= cutoff)
        results_stmt = results_stmt.order_by(col(FlightResult.price).asc()).limit(top_n)

        rows = (await db.execute(results_stmt)).scalars().all()
        out.append(
            AlertResults(
                alert_id=alert.id,
                origin=alert.origin,
                destination=alert.destination,
                is_nonstop_required=alert.is_nonstop_required,
                currency=alert.currency,
                lowest_price=rows[0].price if rows else None,
                results=[FlightResultRead.model_validate(row) for row in rows],
            )
        )
    return out
