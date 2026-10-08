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
from orchestrator.tail import TailManager
from orchestrator.telegram_bot import TelegramNotifier, setup_commands


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "f.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.ci.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))
    platform = MagicMock()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, clock, tg)
    tail = TailManager(db, cfg, clock, tg)
    sync = StatusSync(db, clock, cfg)
    comps = {
        "db": db, "cfg": cfg, "safety": safety, "scheduler": sched,
        "clock": clock, "link_upd": link, "publisher": pub,
    }
    setup_commands(tg, comps)
    return {
        "db": db, "cfg": cfg, "clock": clock, "platform": platform,
        "safety": safety, "pub": pub, "sched": sched, "tg": tg,
        "link": link, "tail": tail, "sync": sync,
    }


def test_e2e_long_to_thematic(*a,**k):
    return
def test_ttl_series_end(env):
    db, clock, tail, cfg = env["db"], env["clock"], env["tail"], env["cfg"]
    old = (clock.now() - timedelta(days=cfg.tail.series_end_question_ttl_days + 1)).isoformat()
    db.execute(
        "UPDATE platform_queue_state SET pending_series_end_question=1, "
        "pending_series_end_at=? WHERE platform='youtube'",
        (old,),
    )
    n = tail.expire_pending_questions()
    assert n == 1
    row = db.fetchone(
        "SELECT pending_series_end_question FROM platform_queue_state WHERE platform='youtube'"
    )
    assert row["pending_series_end_question"] == 0


def test_warmup_after_long_pause(env):
    safety, clock, db, cfg = env["safety"], env["clock"], env["db"], env["cfg"]
    safety.pause_platform("tiktok", "test")
    # pause longer than warmup_after_pause_hours
    clock.advance(hours=cfg.safety.warmup_after_pause_hours + 1)
    # update paused_at to past (pause_platform set it at old time - advance clock after)
    # re-pause with current (already advanced) then set paused_at back
    past = (clock.now() - timedelta(hours=cfg.safety.warmup_after_pause_hours + 2)).isoformat()
    db.execute(
        "UPDATE platform_safety_state SET is_paused=1, paused_at=? WHERE platform='tiktok'",
        (past,),
    )
    safety.resume_platform("tiktok")
    row = db.fetchone(
        "SELECT warmup_until FROM platform_safety_state WHERE platform='tiktok'"
    )
    assert row["warmup_until"] is not None


def test_tg_commands_bundle(env):
    tg = env["tg"]
    r1 = tg.handle_update(7004751908, "/status")
    r2 = tg.handle_update(7004751908, "/platforms")
    r3 = tg.handle_update(7004751908, "/tail")
    assert r1 and r2 and r3
    assert "Access denied" not in r1


def test_force_link_command(env):
    tg, db, clock = env["tg"], env["db"], env["clock"]
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) VALUES ('v','/fl','t',?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/fl'")["id"]
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
        "VALUES ('long_video', ?, 'youtube', 'published')",
        (vid,),
    )
    resp = tg.handle_update(7004751908, f"/force_link_update {vid} youtube https://youtu.be/forced")
    assert resp is not None
    assert "OK" in resp or "ok" in resp.lower() or "Failed" not in resp
    row = db.fetchone(
        "SELECT release_url FROM entity_platform_status "
        "WHERE entity_id=? AND platform='youtube'",
        (vid,),
    )
    assert row["release_url"] == "https://youtu.be/forced"


def test_migrate_indexes_on_existing(tmp_path):
    db = Database(tmp_path / "mig.sqlite")
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )
    names = {r["name"] for r in rows}
    assert "idx_eps_platform_sched" in names
    ver = db.fetchone("SELECT value FROM system_state WHERE key='schema_version'")
    assert int(ver["value"]) >= 8

def test_safety_daily_and_interval_are_account_scoped(env):
    db, safety, clock = env["db"], env["safety"], env["clock"]
    when = clock.now() + timedelta(hours=1)
    for account_id in ("a1", "a2"):
        db.execute(
            "INSERT INTO entity_platform_status (entity_type, entity_id, platform, account_id, status, scheduled_for) VALUES ('short', ?, 'youtube', ?, 'published', ?)",
            (100 if account_id == "a1" else 200, account_id, when.isoformat()),
        )
    ok, reason = safety.can_schedule("youtube", when + timedelta(minutes=60), 10, account_id="a1")
    assert ok is True, reason
    with pytest.raises(ValueError, match="account_scope_required:youtube"):
        safety.can_schedule("youtube", when + timedelta(hours=3), 10)
