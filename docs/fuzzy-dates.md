# Fuzzy date logic

How FlightsScanner turns a user's flexible constraints into the concrete set of
`(departure_date, return_date)` pairs that drive provider queries. Implemented as the pure
function `generate_date_pairs` in [`backend/app/utils/date_logic.py`](../backend/app/utils/date_logic.py)
and unit-tested in [`backend/tests/test_date_logic.py`](../backend/tests/test_date_logic.py).

## 1. Inputs

From a `FlightAlert` (see [database-schema.md](./database-schema.md)):

| Field | Example | Role |
| --- | --- | --- |
| `target_duration_days` | `7` | Ideal trip length. |
| `duration_flexibility_days` | `1` | Allowed ± around the target → 6, 7, 8 days. |
| `earliest_departure_date` | `2026-06-01` | First day you could leave. |
| `latest_departure_date` | `2026-06-10` (optional) | Last day you could leave. |
| `latest_return_date` | `2026-06-20` | Hard cap: you must be back by this date. |

## 2. Algorithm

```
min_duration = target_duration_days - duration_flexibility_days   # >= 1 (validated)
max_duration = target_duration_days + duration_flexibility_days

# Departure window upper bound:
#   - never depart so late that even the shortest trip blows past latest_return_date
derived_latest_dep = latest_return_date - min_duration
dep_window_end = min(latest_departure_date or derived_latest_dep, derived_latest_dep)

pairs = []
for dep in days(earliest_departure_date .. dep_window_end):          # inclusive
    for duration in (min_duration .. max_duration):                  # inclusive
        ret = dep + duration
        if ret <= latest_return_date:
            pairs.append((dep, ret))
return sorted(unique(pairs))
```

Key points:

- **Duration is the inner loop** so each departure date fans out into the allowed trip
  lengths.
- The **return cap is enforced twice**: once by bounding the departure window
  (`derived_latest_dep`) and again per-pair (`ret <= latest_return_date`). The per-pair
  check is what trims the longer durations near the end of the window.
- `latest_departure_date` only ever *narrows* the window; it can never push departures
  past what `latest_return_date` allows.
- Output is **deduplicated and sorted** for stable cache keys and deterministic tests.

## 3. Worked example

Inputs: target `7`, flex `1`, depart `Jun 1 → Jun 10`, return by `Jun 20`.

- Durations: `{6, 7, 8}`.
- `derived_latest_dep = Jun 20 − 6 = Jun 14`; window end = `min(Jun 10, Jun 14) = Jun 10`.
- For each departure `Jun 1 … Jun 10`, emit returns at +6/+7/+8 where `ret ≤ Jun 20`.

| Departure | +6 | +7 | +8 | Pairs kept |
| --- | --- | --- | --- | --- |
| Jun 1 | Jun 7 | Jun 8 | Jun 9 | all 3 |
| Jun 5 | Jun 11 | Jun 12 | Jun 13 | all 3 |
| Jun 10 | Jun 16 | Jun 17 | Jun 18 | all 3 |

→ 10 departures × 3 durations = **30 date pairs**. (Near a tighter return cap, the +8 rows
would drop off first.)

## 4. Edge cases

| Case | Handling |
| --- | --- |
| `duration_flexibility_days = 0` | Single duration = target; one return per departure. |
| `latest_departure_date` omitted | Derive window end from `latest_return_date − min_duration`. |
| Window collapses (earliest > derived end) | Returns `[]`; caller treats as "no work" (and validation should have rejected impossible alerts). |
| `min_duration < 1` | Prevented by schema validation (`flex < target_duration`). Defensive clamp to `1` in code. |
| Same departure reachable twice | `unique()` guarantees no duplicate pairs. |
| Very wide windows | See cost control below. |

## 5. Cost control

The number of pairs is roughly:

$$
N_\text{pairs} \approx (\text{departure window length}) \times (2 \cdot \text{flex} + 1)
$$

Every pair is a *potential* provider call, so this directly drives quota usage. Mitigations
(see [caching-strategy.md](./caching-strategy.md)):

- **Dedupe across alerts**: identical `(origin, destination, dep, ret, nonstop)` queries
  from different alerts share one cache entry.
- **4h TTL**: repeated refreshes within the window are free.
- **Guardrails**: the API validates window sizes and rejects absurd ranges; an optional
  `max_pairs` cap can sample/skip the largest windows.
- Future: prioritize date pairs near the user's `target_duration_days` and only expand to
  the extremes if quota remains.

## 6. Why a pure function

`generate_date_pairs` performs **no I/O** and depends only on its inputs. This makes it:

- trivially unit-testable (deterministic output for given constraints),
- reusable by both the API (to preview/validate) and the worker (to drive fetches),
- safe to call frequently without side effects.
