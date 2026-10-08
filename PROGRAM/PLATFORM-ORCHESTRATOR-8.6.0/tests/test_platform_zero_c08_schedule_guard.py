"""platform-zero COMMIT 8: ScheduleGuard = EPS (+ optional sources); no required platform_source."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.clock import FakeClock  # noqa: E402
from orchestrator.config import load_config  # noqa: E402
from orchestrator.db import Database  # noqa: E402
from orchestrator.schedule_guard import ScheduleGuard, eps_source  # noqa: E402


def _cfg():
    for name in ("config.ci.yaml", "config.example.yaml"):
        path = ROOT / name
        if path.is_file():
            return load_config(path)
    raise RuntimeError("no config")


def test_eps_source_reads_scheduled(tmp_path):
    db = Database(tmp_path / "g.sqlite")
    when = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, scheduled_for) "
        "VALUES ('short', 1, 'youtube', 'scheduled', ?)",
        (when.isoformat(),),
    )
    fn = eps_source(db)
    times = fn("youtube")
    assert any(abs((t - when).total_seconds()) < 1 for t in times)


def test_guard_conflict_from_eps_only(tmp_path):
    cfg = _cfg()
    db = Database(tmp_path / "g2.sqlite")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    when = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, scheduled_for) "
        "VALUES ('short', 1, 'youtube', 'scheduled', ?)",
        (when.isoformat(),),
    )
    guard = ScheduleGuard(cfg, clock, sources=[("eps", eps_source(db))])
    # same slot → conflict
    reason = guard.conflict("youtube", when)
    assert reason is not None and "schedule_conflict" in reason
    # far slot → ok
    far = when + timedelta(hours=5)
    assert guard.conflict("youtube", far) is None


def test_guard_works_without_platform_source(tmp_path):
    """C8: no platform_source required."""
    cfg = _cfg()
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    guard = ScheduleGuard(cfg, clock, sources=[])  # empty is fine
    assert guard.conflict("youtube", datetime(2026, 3, 10, 16, 0, tzinfo=UTC)) is None
