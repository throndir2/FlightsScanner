"""Fuzzy date logic.

Turns a user's flexible constraints into the concrete set of ``(departure, return)`` date
pairs that drive provider queries. This module is **pure** — it performs no I/O and depends
only on its inputs, so it is fast, deterministic, and trivially unit-testable.

See ``docs/fuzzy-dates.md`` for the algorithm, worked examples, and edge cases.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple, Protocol, runtime_checkable


class DatePair(NamedTuple):
    """A concrete itinerary candidate."""

    departure_date: date
    return_date: date

    @property
    def duration_days(self) -> int:
        return (self.return_date - self.departure_date).days


@runtime_checkable
class DatePairConfig(Protocol):
    """Structural type for anything that can drive date-pair generation.

    Satisfied by both the :class:`~app.models.flight_alert.FlightAlert` table model and the
    :class:`~app.schemas.alert.FlightAlertBase` DTO (and by test fixtures).
    """

    target_duration_days: int
    duration_flexibility_days: int
    earliest_departure_date: date
    latest_departure_date: date | None
    latest_return_date: date


def generate_date_pairs(
    alert_config: DatePairConfig,
    *,
    max_pairs: int | None = None,
) -> list[DatePair]:
    """Expand fuzzy constraints into every valid ``(departure, return)`` pair.

    The algorithm:

    1. Compute the duration band ``[target - flex, target + flex]`` (min clamped to 1).
    2. Bound the departure window above so even the *shortest* trip returns on or before
       ``latest_return_date``; narrow further with ``latest_departure_date`` if provided.
    3. For each departure day in the window, emit a pair for each duration in the band whose
       return date does not exceed ``latest_return_date``.

    Args:
        alert_config: Object exposing the fuzzy-constraint attributes.
        max_pairs: Optional cap. When the full expansion exceeds this, pairs closest to the
            user's ``target_duration_days`` are kept (most relevant first), then re-sorted
            chronologically. Guards against combinatorial blow-ups (see config
            ``MAX_DATE_PAIRS_PER_ALERT``).

    Returns:
        A chronologically sorted, de-duplicated list of :class:`DatePair`. Empty if the
        window admits no feasible pair.
    """
    target = alert_config.target_duration_days
    flex = alert_config.duration_flexibility_days

    min_duration = max(1, target - flex)
    max_duration = target + flex

    # Latest departure such that the shortest trip still returns within the hard cap.
    derived_latest_departure = alert_config.latest_return_date - timedelta(days=min_duration)
    latest_departure = derived_latest_departure
    if alert_config.latest_departure_date is not None:
        latest_departure = min(alert_config.latest_departure_date, derived_latest_departure)

    pairs: list[DatePair] = []
    seen: set[tuple[date, date]] = set()

    departure = alert_config.earliest_departure_date
    while departure <= latest_departure:
        for duration in range(min_duration, max_duration + 1):
            return_date = departure + timedelta(days=duration)
            if return_date <= alert_config.latest_return_date:
                key = (departure, return_date)
                if key not in seen:
                    seen.add(key)
                    pairs.append(DatePair(departure, return_date))
        departure += timedelta(days=1)

    if max_pairs is not None and len(pairs) > max_pairs:
        # Keep the pairs whose duration is closest to the user's ideal, then restore order.
        pairs.sort(
            key=lambda p: (abs(p.duration_days - target), p.departure_date, p.return_date)
        )
        pairs = pairs[:max_pairs]

    pairs.sort()
    return pairs
