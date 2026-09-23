from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.safety import SafetyChecker


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.sqlite")
    d.ensure_platform_states(["youtube", "tiktok"])
    return d


@pytest.fixture
def cfg():
    return load_config(Path(__file__).resolve().parents[1] / "config.yaml")


@pytest.fixture
def clock():
    return FakeClock(datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC))


@pytest.fixture
def safety(db, cfg, clock):
    return SafetyChecker(db, cfg, clock)


def test_daily_limit_future_date(db, safety, clock):
    platform = "youtube"
    # insert 7 posts on 2026-03-12
    base = datetime(2026, 3, 12, 10, 0, tzinfo=UTC)
    for i in range(7):
        db.execute(
            """
            INSERT INTO entity_platform_status
                (entity_type, entity_id, platform, status, postiz_scheduled_for)
            VALUES ('long_video', ?, ?, 'scheduled', ?)
            """,
            (i + 1, platform, (base + timedelta(hours=i)).isoformat()),
        )
    ok, reason = safety.can_schedule(
        platform, datetime(2026, 3, 12, 20, 0, tzinfo=UTC), 7
    )
    assert not ok
    assert "daily_limit" in reason

    ok2, _ = safety.can_schedule(
        platform, datetime(2026, 3, 13, 10, 0, tzinfo=UTC), 7
    )
    assert ok2


def test_min_interval(db, safety):
    platform = "tiktok"
    t1 = datetime(2026, 3, 10, 14, 0, tzinfo=UTC)
    db.execute(
        """
        INSERT INTO entity_platform_status
            (entity_type, entity_id, platform, status, postiz_scheduled_for)
        VALUES ('short', 1, ?, 'scheduled', ?)
        """,
        (platform, t1.isoformat()),
    )
    ok, reason = safety.can_schedule(
        platform, t1 + timedelta(minutes=10), 10
    )
    assert not ok
    assert "min_interval" in reason

    ok2, _ = safety.can_schedule(
        platform, t1 + timedelta(minutes=30), 10
    )
    assert ok2


def test_pause(safety, db):
    safety.pause_platform("youtube", "test")
    assert safety.is_platform_paused("youtube")
    safety.resume_platform("youtube")
    assert not safety.is_platform_paused("youtube")
