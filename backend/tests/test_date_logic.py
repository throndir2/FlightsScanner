"""Unit tests for the pure fuzzy date logic (``app.utils.date_logic``).

These tests are deterministic and I/O-free — they are the canonical specification of the
date-pair expansion described in ``docs/fuzzy-dates.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.utils.date_logic import DatePair, generate_date_pairs


@dataclass
class Cfg:
    """Minimal structural stand-in for a FlightAlert (satisfies ``DatePairConfig``)."""

    target_duration_days: int
    duration_flexibility_days: int
    earliest_departure_date: date
    latest_return_date: date
    latest_departure_date: date | None = None


def _durations(pairs: list[DatePair]) -> set[int]:
    return {p.duration_days for p in pairs}


def test_worked_example_from_docs() -> None:
    # Target 7 ± 1, depart Jun 1–10, return by Jun 20  → 10 departures × 3 durations.
    cfg = Cfg(7, 1, date(2026, 6, 1), date(2026, 6, 20), date(2026, 6, 10))
    pairs = generate_date_pairs(cfg)

    assert len(pairs) == 30
    assert _durations(pairs) == {6, 7, 8}
    assert pairs[0] == DatePair(date(2026, 6, 1), date(2026, 6, 7))  # earliest dep, shortest
    assert DatePair(date(2026, 6, 10), date(2026, 6, 18)) in pairs  # latest dep, longest


def test_zero_flexibility_single_duration() -> None:
    cfg = Cfg(5, 0, date(2026, 6, 1), date(2026, 6, 10), date(2026, 6, 3))
    pairs = generate_date_pairs(cfg)

    assert _durations(pairs) == {5}
    assert pairs == [
        DatePair(date(2026, 6, 1), date(2026, 6, 6)),
        DatePair(date(2026, 6, 2), date(2026, 6, 7)),
        DatePair(date(2026, 6, 3), date(2026, 6, 8)),
    ]


def test_latest_departure_derived_when_absent() -> None:
    # No explicit latest_departure_date → derived from latest_return_date - min_duration.
    cfg = Cfg(7, 0, date(2026, 6, 1), date(2026, 6, 10))
    pairs = generate_date_pairs(cfg)

    # derived latest departure = Jun 10 - 7 = Jun 3 → departures Jun 1, 2, 3.
    assert pairs == [
        DatePair(date(2026, 6, 1), date(2026, 6, 8)),
        DatePair(date(2026, 6, 2), date(2026, 6, 9)),
        DatePair(date(2026, 6, 3), date(2026, 6, 10)),
    ]


def test_return_cap_trims_longer_durations_near_window_end() -> None:
    # Target 7 ± 2 (durations 5–9), depart Jun 1–5, return by Jun 10.
    cfg = Cfg(7, 2, date(2026, 6, 1), date(2026, 6, 10), date(2026, 6, 5))
    pairs = generate_date_pairs(cfg)

    # Jun1:5, Jun2:4, Jun3:3, Jun4:2, Jun5:1  → 15 pairs.
    assert len(pairs) == 15
    # Every kept pair must respect the hard return cap.
    assert all(p.return_date <= date(2026, 6, 10) for p in pairs)


def test_latest_departure_only_narrows_window() -> None:
    # An explicit latest_departure_date later than the derived bound must not widen it.
    cfg = Cfg(7, 0, date(2026, 6, 1), date(2026, 6, 10), date(2026, 6, 30))
    pairs = generate_date_pairs(cfg)

    # Still capped at the derived Jun 3 departure.
    assert max(p.departure_date for p in pairs) == date(2026, 6, 3)


def test_infeasible_window_returns_empty() -> None:
    cfg = Cfg(7, 0, date(2026, 6, 20), date(2026, 6, 10))
    assert generate_date_pairs(cfg) == []


def test_output_is_sorted_and_unique() -> None:
    cfg = Cfg(7, 2, date(2026, 6, 1), date(2026, 7, 1), date(2026, 6, 15))
    pairs = generate_date_pairs(cfg)

    assert pairs == sorted(pairs)
    assert len(pairs) == len(set(pairs))


def test_max_pairs_keeps_durations_closest_to_target() -> None:
    cfg = Cfg(7, 1, date(2026, 6, 1), date(2026, 6, 20), date(2026, 6, 10))
    pairs = generate_date_pairs(cfg, max_pairs=10)

    # 30 candidates capped to 10; the 10 duration-7 pairs (|dur-target|=0) win.
    assert len(pairs) == 10
    assert _durations(pairs) == {7}
    assert pairs == sorted(pairs)  # re-sorted chronologically after capping


def test_max_pairs_above_total_returns_all() -> None:
    cfg = Cfg(7, 1, date(2026, 6, 1), date(2026, 6, 20), date(2026, 6, 10))
    assert len(generate_date_pairs(cfg, max_pairs=999)) == 30


def test_datepair_duration_property() -> None:
    assert DatePair(date(2026, 6, 1), date(2026, 6, 8)).duration_days == 7


@pytest.mark.parametrize(
    ("target", "flex", "expected_durations"),
    [
        (7, 0, {7}),
        (7, 1, {6, 7, 8}),
        (10, 3, {7, 8, 9, 10, 11, 12, 13}),
    ],
)
def test_duration_band(target: int, flex: int, expected_durations: set[int]) -> None:
    cfg = Cfg(target, flex, date(2026, 6, 1), date(2026, 9, 1), date(2026, 6, 15))
    assert _durations(generate_date_pairs(cfg)) == expected_durations
