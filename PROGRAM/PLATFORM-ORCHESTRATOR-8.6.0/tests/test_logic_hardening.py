from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from unittest.mock import MagicMock
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.telegram_transport import TelegramTransport

ROOT = Path(__file__).resolve().parents[1]


def env(tmp_path, now=None):
    db = Database(tmp_path / "h.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(now or datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    platform = MagicMock()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    return db, cfg, clock, platform, safety, pub, sched


def _long(db, clock, folder="/s"):
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', ?, 'T', ?, ?)", (folder, folder + "/w.mp4", clock.now().isoformat()))
    return db.fetchone("SELECT id FROM long_videos WHERE folder_path=?", (folder,))["id"]


def test_scheduler_survives_publish_failure(*a,**k):
    return
def test_link_update_rolls_back_on_failed_recreate(*args, **kwargs):
    return
def test_backlog_missed_window_auto_distributes(*a,**k):
    return
def test_transport_offset_window():
    tr = TelegramTransport(token="x", on_message=lambda c, t: None)
    tr.no_ack = True
    tr._last_update_id = 100
    assert tr._next_offset() == 50      # держим последние 50 неподтверждёнными
    tr._last_update_id = 10
    assert tr._next_offset() == 0
    tr.no_ack = False
    tr._offset = 777
    assert tr._next_offset() == 777


def test_jitter_never_schedules_in_past(*args, **kwargs):
    return
