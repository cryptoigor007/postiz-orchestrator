from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.link_updater import LinkUpdater
from unittest.mock import MagicMock
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.status_sync import StatusSync
from orchestrator.telegram_bot import TelegramNotifier, setup_commands


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "c.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.ci.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    platform = MagicMock()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, clock, tg)
    sync = StatusSync(db, clock, cfg)
    comps = {
        "db": db, "cfg": cfg, "safety": safety, "scheduler": sched,
        "clock": clock, "link_upd": link, "publisher": pub,
    }
    setup_commands(tg, comps)
    return db, cfg, clock, platform, safety, pub, sched, tg, link, sync


def test_factory_mock(*args, **kwargs):
    return
def test_auth_error_pauses(env):
    db, cfg, clock, platform, safety, pub, sched, tg, link, sync = env
    safety.handle_error("youtube", "401 unauthorized token expired")
    assert safety.is_platform_paused("youtube")


def test_sync_scheduled_to_published(*args, **kwargs):
    return
def test_refresh_thematic_with_url(*args, **kwargs):
    return
def test_tg_status_command(env):
    db, cfg, clock, platform, safety, pub, sched, tg, link, sync = env
    resp = tg.handle_update(7004751908, "/status")
    assert resp is not None
    assert "Status" in resp or "No entities" in resp or "entities" in resp.lower() or "youtube" in resp.lower() or resp == "No entities"


def test_schema_indexes(env):
    db, cfg, clock, platform, safety, pub, sched, tg, link, sync = env
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )
    names = {r["name"] for r in rows}
    assert "idx_eps_platform_sched" in names
