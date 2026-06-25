"""API integration tests exercising the real app over the full request path.

Uses the ``api`` fixture (in-memory async SQLite, stubbed enqueue, fixed test user). These
assert the contract in ``docs/api-spec.md`` end-to-end.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from httpx import AsyncClient

VALID_ALERT = {
    "origin": "JFK",
    "destination": "LHR",
    "target_duration_days": 7,
    "duration_flexibility_days": 1,
    "earliest_departure_date": "2026-06-01",
    "latest_departure_date": "2026-06-10",
    "latest_return_date": "2026-06-20",
    "is_nonstop_required": True,
    "cabin_class": "economy",
    "currency": "USD",
}

INFEASIBLE_ALERT = {
    **VALID_ALERT,
    "earliest_departure_date": "2026-06-20",
    "latest_departure_date": None,
    "latest_return_date": "2026-06-21",  # too early for a 6-day minimum trip
}


async def _create(client: AsyncClient, **overrides) -> dict:
    payload = {**VALID_ALERT, **overrides}
    resp = await client.post("/api/alerts", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_health(api: tuple[AsyncClient, UUID]) -> None:
    client, _ = api
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_create_alert(api: tuple[AsyncClient, UUID]) -> None:
    client, user_id = api
    body = await _create(client)
    assert body["origin"] == "JFK"
    assert body["destination"] == "LHR"
    assert body["user_id"] == str(user_id)
    assert body["is_active"] is True


async def test_create_alert_normalizes_iata(api: tuple[AsyncClient, UUID]) -> None:
    client, _ = api
    body = await _create(client, origin="jfk", destination="lhr")
    assert body["origin"] == "JFK"
    assert body["destination"] == "LHR"


async def test_create_alert_infeasible_returns_422(api: tuple[AsyncClient, UUID]) -> None:
    client, _ = api
    resp = await client.post("/api/alerts", json=INFEASIBLE_ALERT)
    assert resp.status_code == 422


async def test_list_alerts(api: tuple[AsyncClient, UUID]) -> None:
    client, user_id = api
    await _create(client)
    await _create(client, destination="CDG")
    resp = await client.get(f"/api/alerts/{user_id}")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_alerts_forbidden_for_other_user(api: tuple[AsyncClient, UUID]) -> None:
    client, _ = api
    resp = await client.get(f"/api/alerts/{uuid4()}")
    assert resp.status_code == 403
    assert resp.json()["code"] == "forbidden"


async def test_results_empty_when_no_refresh(api: tuple[AsyncClient, UUID]) -> None:
    client, user_id = api
    await _create(client)
    resp = await client.get(f"/api/alerts/{user_id}/results")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["lowest_price"] is None
    assert data[0]["results"] == []


async def test_results_forbidden_for_other_user(api: tuple[AsyncClient, UUID]) -> None:
    client, _ = api
    resp = await client.get(f"/api/alerts/{uuid4()}/results")
    assert resp.status_code == 403
    assert resp.json()["code"] == "forbidden"


async def test_update_alert_pause(api: tuple[AsyncClient, UUID]) -> None:
    client, _ = api
    alert_id = (await _create(client))["id"]
    resp = await client.patch(f"/api/alerts/{alert_id}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_update_alert_infeasible_returns_422(api: tuple[AsyncClient, UUID]) -> None:
    client, _ = api
    alert_id = (await _create(client))["id"]
    # 60-day target with the existing June window is infeasible.
    resp = await client.patch(f"/api/alerts/{alert_id}", json={"target_duration_days": 60})
    assert resp.status_code == 422
    assert resp.json()["code"] == "invalid_constraints"


async def test_update_alert_not_found(api: tuple[AsyncClient, UUID]) -> None:
    client, _ = api
    resp = await client.patch(f"/api/alerts/{uuid4()}", json={"is_active": False})
    assert resp.status_code == 404


async def test_delete_alert(api: tuple[AsyncClient, UUID]) -> None:
    client, user_id = api
    alert_id = (await _create(client))["id"]
    resp = await client.delete(f"/api/alerts/{alert_id}")
    assert resp.status_code == 204
    listing = await client.get(f"/api/alerts/{user_id}")
    assert listing.json() == []


async def test_manual_refresh_accepted(api: tuple[AsyncClient, UUID]) -> None:
    client, _ = api
    alert_id = (await _create(client))["id"]
    resp = await client.post(f"/api/alerts/{alert_id}/refresh")
    assert resp.status_code == 202
    assert resp.json()["status"] == "scheduled"
