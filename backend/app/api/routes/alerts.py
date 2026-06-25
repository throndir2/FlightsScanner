"""Alert endpoints: create a tracking configuration and read cached results."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.errors import APIError
from app.models.user import User
from app.schemas.alert import (
    FlightAlertCreate,
    FlightAlertRead,
    FlightAlertUpdate,
    validate_alert_constraints,
)
from app.schemas.result import AlertResults
from app.services import alert_service
from app.services.dispatch import enqueue_alert_refresh

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("", response_model=FlightAlertRead, status_code=201)
async def create_alert(
    payload: FlightAlertCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FlightAlertRead:
    """Create a flexible tracking configuration and seed an initial background refresh.

    The owner is bound from the session; constraint validation happens in the schema
    (infeasible windows are rejected with 422). See ``docs/api-spec.md``.
    """
    alert = await alert_service.create_alert(db, user_id=user.id, payload=payload)
    # Commit before enqueueing so the worker can't race ahead of the write.
    await db.commit()

    try:
        enqueue_alert_refresh(alert.id)
    except Exception:  # broker hiccup must not fail creation — Beat will catch up
        logger.warning("Failed to enqueue initial refresh for alert %s", alert.id, exc_info=True)

    return FlightAlertRead.model_validate(alert)


@router.get("/{user_id}/results", response_model=list[AlertResults])
async def get_results(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    top_n: int = Query(1, ge=1, le=10, description="Cheapest N date pairs per alert"),
    include_stale: bool = Query(True, description="Include results older than the cache TTL"),
    alert_id: UUID | None = Query(None, description="Restrict to a single alert"),
) -> list[AlertResults]:
    """Return the lowest cached prices for the user's active alerts (no provider calls)."""
    if user_id != user.id:
        raise APIError(403, "You do not have access to these results", "forbidden")

    return await alert_service.get_results_for_user(
        db,
        user_id=user_id,
        top_n=top_n,
        include_stale=include_stale,
        alert_id=alert_id,
    )


@router.get("/{user_id}", response_model=list[FlightAlertRead])
async def list_alerts(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FlightAlertRead]:
    """List all alerts owned by the authenticated user."""
    if user_id != user.id:
        raise APIError(403, "You do not have access to these alerts", "forbidden")
    alerts = await alert_service.list_alerts(db, user_id=user_id)
    return [FlightAlertRead.model_validate(a) for a in alerts]


@router.patch("/{alert_id}", response_model=FlightAlertRead)
async def update_alert(
    alert_id: UUID,
    payload: FlightAlertUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FlightAlertRead:
    """Update constraints or pause/resume an alert. Re-validates feasibility on the merge."""
    alert = await alert_service.get_owned_alert(db, user_id=user.id, alert_id=alert_id)
    if alert is None:
        raise APIError(404, "Alert not found", "not_found")

    data = payload.model_dump(exclude_unset=True)

    def merged(field: str):
        provided = data.get(field)
        return provided if provided is not None else getattr(alert, field)

    latest_departure = (
        data["latest_departure_date"]
        if "latest_departure_date" in data
        else alert.latest_departure_date
    )
    try:
        validate_alert_constraints(
            origin=merged("origin"),
            destination=merged("destination"),
            target_duration_days=merged("target_duration_days"),
            duration_flexibility_days=merged("duration_flexibility_days"),
            earliest_departure_date=merged("earliest_departure_date"),
            latest_departure_date=latest_departure,
            latest_return_date=merged("latest_return_date"),
        )
    except ValueError as exc:
        raise APIError(422, str(exc), "invalid_constraints") from exc

    updated = await alert_service.apply_alert_update(db, alert=alert, data=data)
    await db.commit()
    return FlightAlertRead.model_validate(updated)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Stop tracking and delete an alert (cascades to its cached results)."""
    alert = await alert_service.get_owned_alert(db, user_id=user.id, alert_id=alert_id)
    if alert is None:
        raise APIError(404, "Alert not found", "not_found")
    await alert_service.delete_alert(db, alert=alert)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{alert_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_alert_now(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Force a refresh now (bypasses freshness, still honors the daily quota guard)."""
    alert = await alert_service.get_owned_alert(db, user_id=user.id, alert_id=alert_id)
    if alert is None:
        raise APIError(404, "Alert not found", "not_found")
    try:
        enqueue_alert_refresh(alert.id, force=True)
    except Exception as exc:  # broker unreachable
        raise APIError(
            503, "Could not enqueue refresh (broker unavailable)", "broker_unavailable"
        ) from exc
    return {"status": "scheduled", "alert_id": str(alert.id)}
