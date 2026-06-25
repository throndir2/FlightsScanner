# API specification

REST contract between the Next.js frontend and the FastAPI backend. All endpoints are
served under `/api`. FastAPI auto-generates OpenAPI at `/docs` and `/openapi.json`.

For data shapes see [database-schema.md](./database-schema.md); for auth see
[auth-and-security.md](./auth-and-security.md).

## Conventions

- **Content type:** `application/json` for requests and responses.
- **Dates:** ISO-8601 `YYYY-MM-DD`. Timestamps are RFC 3339 UTC.
- **IDs:** UUID v4 strings.
- **Auth:** the frontend forwards the NextAuth session as a bearer token; the backend
  resolves the current user via a dependency. Ownership is enforced server-side.
- **Errors:** a consistent envelope:
  ```json
  { "detail": "human-readable message", "code": "machine_code" }
  ```

| Status | Meaning |
| --- | --- |
| `200` | OK (reads) |
| `201` | Created (alert) |
| `400` | Malformed request (e.g. bad `X-User-Id`) |
| `401` | Missing/invalid session |
| `403` | Authenticated but not the resource owner |
| `404` | Resource not found |
| `422` | Body failed schema validation — **including infeasible constraint combinations** (FastAPI/Pydantic default shape) |
| `503` | Downstream (DB/Redis) unavailable |

---

## Endpoints

### `GET /api/health`

Liveness/readiness probe. No auth.

**200**
```json
{ "status": "ok", "service": "flightsscanner-api", "version": "0.1.0" }
```

---

### `POST /api/alerts`

Create a flexible tracking configuration. On success the backend persists the alert and
**enqueues an initial background refresh** (non-blocking).

**Request body — `FlightAlertCreate`**
```json
{
  "origin": "JFK",
  "destination": "LHR",
  "target_duration_days": 7,
  "duration_flexibility_days": 1,
  "earliest_departure_date": "2026-06-01",
  "latest_departure_date": "2026-06-10",
  "latest_return_date": "2026-06-20",
  "is_nonstop_required": true,
  "max_stops": null,
  "cabin_class": "economy",
  "currency": "USD"
}
```

**Field rules**

| Field | Rule |
| --- | --- |
| `origin`, `destination` | 3-letter IATA, uppercase, `origin != destination`. |
| `target_duration_days` | integer ≥ 1. |
| `duration_flexibility_days` | integer ≥ 0 and `< target_duration_days`. |
| `earliest_departure_date` | a valid date (a "not in the past" rule is intentionally **not** enforced in v1 to keep demos/tests time-independent; add it in production). |
| `latest_departure_date` | optional; `≥ earliest_departure_date` and `≤ latest_return_date`. |
| `latest_return_date` | `≥ earliest_departure_date + (target − flex)`. |
| `is_nonstop_required` | boolean; if `true`, `max_stops` ignored. |
| `cabin_class` | one of `economy`, `premium_economy`, `business`, `first`. |
| `currency` | ISO-4217. |

**201 — `FlightAlertRead`**
```json
{
  "id": "8f7c…",
  "user_id": "1a2b…",
  "origin": "JFK",
  "destination": "LHR",
  "target_duration_days": 7,
  "duration_flexibility_days": 1,
  "earliest_departure_date": "2026-06-01",
  "latest_departure_date": "2026-06-10",
  "latest_return_date": "2026-06-20",
  "is_nonstop_required": true,
  "max_stops": null,
  "cabin_class": "economy",
  "currency": "USD",
  "is_active": true,
  "created_at": "2026-06-25T12:00:00Z",
  "updated_at": "2026-06-25T12:00:00Z"
}
```

**422** — invalid or infeasible constraints. Cross-field rules (e.g. `latest_return_date`
too early for the minimum trip length, `origin == destination`, or
`duration_flexibility_days >= target_duration_days`) are enforced by the request schema and
return FastAPI's standard validation shape:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Value error, latest_return_date is earlier than the minimum trip allows"
    }
  ]
}
```

> The `{ "detail", "code" }` envelope documented above applies to errors the application
> raises explicitly (401/403/400). Pydantic body-validation failures use the array shape
> shown here.

---

### `GET /api/alerts/{user_id}/results`

Return the **lowest cached price** matching each of the user's active alerts. Reads only
from Postgres/Redis — never triggers a provider call.

**Path params**

| Param | Type | Notes |
| --- | --- | --- |
| `user_id` | UUID | Must equal the authenticated user (else `403`). |

**Query params**

| Param | Type | Default | Notes |
| --- | --- | --- | --- |
| `top_n` | int | `1` | Cheapest N date pairs per alert (1–10). |
| `include_stale` | bool | `true` | Include results older than the cache TTL. |
| `alert_id` | UUID | — | Restrict to a single alert. |

**200 — list of `AlertResults`**
```json
[
  {
    "alert_id": "8f7c…",
    "origin": "JFK",
    "destination": "LHR",
    "is_nonstop_required": true,
    "currency": "USD",
    "lowest_price": 412.50,
    "results": [
      {
        "departure_date": "2026-06-03",
        "return_date": "2026-06-10",
        "price": 412.50,
        "currency": "USD",
        "carrier": "VS",
        "stops": 0,
        "is_nonstop": true,
        "deep_link": "https://book.example.com/…",
        "provider": "mock",
        "fetched_at": "2026-06-25T11:32:00Z"
      }
    ]
  }
]
```

If an alert has no cached results yet (refresh still pending), it appears with
`lowest_price: null` and an empty `results` array.

**403**
```json
{ "detail": "You do not have access to these results", "code": "forbidden" }
```

---

### `GET /api/alerts/{user_id}`

List all alerts owned by the authenticated user (newest first). `user_id` must equal the
session user, else `403`.

**200** — list of `FlightAlertRead` (same shape as the create response).

---

### `PATCH /api/alerts/{alert_id}`

Update constraints or pause/resume an alert. Body is a **partial** `FlightAlertUpdate` —
every field optional; only provided fields change. The merged record is re-checked for
feasibility.

**Request body (example)**
```json
{ "is_active": false }
```

**200** — the updated `FlightAlertRead`.
**404** — `{ "detail": "Alert not found", "code": "not_found" }` (also when not owned).
**422** — invalid field, or an infeasible merged constraint set
(`{ "detail": "...", "code": "invalid_constraints" }`).

---

### `DELETE /api/alerts/{alert_id}`

Stop tracking and delete an alert (cascades to its cached results).

**204** — no content.
**404** — not found or not owned.

---

### `POST /api/alerts/{alert_id}/refresh`

Force a refresh **now**. Bypasses the per-pair freshness cache check but still honors the
daily provider quota guard (see [caching-strategy.md](./caching-strategy.md)).

**202**
```json
{ "status": "scheduled", "alert_id": "8f7c…" }
```
**404** — not found or not owned.
**503** — `{ "detail": "Could not enqueue refresh (broker unavailable)", "code": "broker_unavailable" }`.

---

## Future endpoints (roadmap)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/alerts/{alert_id}/history` | Price history for charts. |
| `POST` | `/api/alerts/{alert_id}/notifications` | Configure price-drop alerts. |

## OpenAPI

The authoritative, always-current schema is generated by FastAPI. With the stack running:

- Swagger UI: `http://localhost:8000/docs`
- Raw schema: `http://localhost:8000/openapi.json`
