from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.slots import (
    next_long_video_dates,
    thematic_slot_days,
)


def test_thematic_slots_basic():
    long_dt = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)  # Tue
    next_dt = datetime(2026, 3, 13, 16, 0, tzinfo=UTC)  # Fri
    slots = thematic_slot_days(long_dt, next_dt, "20:30")
    assert len(slots) == 3  # 10,11,12
    assert slots[0].day == 10
    assert slots[0].hour == 17  # 20:30 MSK = 17:30 UTC
    assert slots[-1].day == 12


def test_thematic_slots_no_next():
    long_dt = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    slots = thematic_slot_days(long_dt, None, "20:30")
    assert len(slots) == 1
    assert slots[0].day == 10


def test_next_long_dates():
    from_dt = datetime(2026, 3, 9, 12, 0, tzinfo=UTC)
    dates = next_long_video_dates(["tue", "fri"], "16:00", from_dt, count=4)
    assert len(dates) == 4
    assert dates[0].weekday() in (1, 4)  # tue=1, fri=4
    assert all(d > from_dt for d in dates)
