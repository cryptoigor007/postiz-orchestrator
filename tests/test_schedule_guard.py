from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.schedule_guard import ScheduleGuard

ROOT = Path(__file__).resolve().parents[1]


def make(tmp_path, busy):
    cfg = load_config(ROOT / "config.yaml")
    cfg.safety.min_interval_minutes = 25
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    calls = {"n": 0}

    def src(platform):
        calls["n"] += 1
        return busy

    g = ScheduleGuard(cfg, clock, sources=[("fake", src)], ttl_sec=60)
    return g, calls, clock


def test_conflict_detected_and_cached(tmp_path):
    busy = [datetime(2026, 3, 10, 16, 10, tzinfo=UTC)]
    g, calls, clock = make(tmp_path, busy)
    assert g.conflict("youtube", datetime(2026, 3, 10, 16, 0, tzinfo=UTC)) is not None
    assert g.conflict("youtube", datetime(2026, 3, 10, 16, 0, tzinfo=UTC)) is not None
    assert calls["n"] == 1  # кэш: источник опрошен один раз


def test_no_conflict_when_far(tmp_path):
    busy = [datetime(2026, 3, 10, 10, 0, tzinfo=UTC)]
    g, calls, clock = make(tmp_path, busy)
    assert g.conflict("youtube", datetime(2026, 3, 10, 16, 0, tzinfo=UTC)) is None
    # на следующий день — ок
    assert g.conflict("youtube", datetime(2026, 3, 11, 10, 0, tzinfo=UTC)) is None


def test_source_failure_is_safe(tmp_path):
    cfg = load_config(ROOT / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))

    def bad(platform):
        raise RuntimeError("postiz down")

    g = ScheduleGuard(cfg, clock, sources=[("bad", bad)])
    assert g.conflict("youtube", datetime(2026, 3, 10, 16, 0, tzinfo=UTC)) is None


def test_publisher_blocks_on_guard_conflict(tmp_path):
    from orchestrator.db import Database
    from orchestrator.postiz import MockPostizClient
    from orchestrator.publisher import Publisher
    from orchestrator.safety import SafetyChecker

    db = Database(tmp_path / "p.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    guard = ScheduleGuard(cfg, clock, sources=[("fake", lambda p: [datetime(2026, 3, 10, 16, 0, tzinfo=UTC)])])
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False, guard=guard)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v','/g','t','/g/w.mp4',?)", (clock.now().isoformat(),))
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    sched = datetime(2026, 3, 10, 16, 5, tzinfo=UTC)
    assert pub.publish("long_video", vid, "youtube", "/g/w.mp4", {"title": "x"}, sched) is None
    log = db.fetchone(
        "SELECT details FROM publish_log WHERE action='safety_block' ORDER BY id DESC LIMIT 1")
    assert log and log["details"].startswith("schedule_conflict")


def test_conflict_window_configurable(tmp_path):
    busy = [datetime(2026, 3, 10, 16, 30, tzinfo=UTC)]
    g, _, _ = make(tmp_path, busy)
    assert g.conflict("youtube", datetime(2026, 3, 10, 16, 0, tzinfo=UTC)) is None  # 30 мин > 25
    g.cfg.safety.conflict_window_minutes = 60
    g._cache.clear()
    assert g.conflict("youtube", datetime(2026, 3, 10, 16, 0, tzinfo=UTC)) is not None
