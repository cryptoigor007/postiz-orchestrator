from __future__ import annotations
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.slots import local_to_utc, next_long_video_dates, thematic_slot_days
from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.safety import SafetyChecker


def test_msk_wall_to_utc():
    from datetime import date, time
    utc = local_to_utc(date(2026, 3, 10), time(16, 0), "Europe/Moscow")
    # MSK = UTC+3 → 13:00 UTC
    assert utc.hour == 13
    assert utc.tzinfo == timezone.utc


def test_next_long_in_msk():
    from_dt = datetime(2026, 3, 9, 10, 0, tzinfo=timezone.utc)
    dates = next_long_video_dates(
        ["tue", "fri"], "16:00", from_dt, count=2, tz_name="Europe/Moscow"
    )
    assert len(dates) == 2
    # 16:00 MSK = 13:00 UTC
    assert all(d.hour == 13 for d in dates)


def test_auto_resume(tmp_path):
    db = Database(tmp_path / "a.sqlite")
    db.ensure_platform_states(["youtube"])
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    # force pause_hours = 1 for test
    cfg.safety.on_serious_error["pause_hours"] = 1
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc))
    safety = SafetyChecker(db, cfg, clock)
    safety.pause_platform("youtube", "test")
    assert safety.is_platform_paused("youtube")
    # still paused after 30 min
    clock.advance(minutes=30)
    assert safety.is_platform_paused("youtube")
    # after 1h+ resumed
    clock.advance(minutes=40)
    assert not safety.is_platform_paused("youtube")


def test_schema_version(tmp_path):
    db = Database(tmp_path / "s.sqlite")
    row = db.fetchone("SELECT value FROM system_state WHERE key='schema_version'")
    assert row is not None
    assert int(row["value"]) >= 7
