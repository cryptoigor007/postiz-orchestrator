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
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.status_sync import StatusSync
from orchestrator.tail import TailManager
from orchestrator.telegram_bot import TelegramNotifier, setup_commands


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "f.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, postiz, clock, tg)
    tail = TailManager(db, cfg, clock, tg)
    sync = StatusSync(db, postiz, clock, cfg)
    comps = {
        "db": db, "cfg": cfg, "safety": safety, "scheduler": sched,
        "clock": clock, "link_upd": link, "publisher": pub,
    }
    setup_commands(tg, comps)
    return {
        "db": db, "cfg": cfg, "clock": clock, "postiz": postiz,
        "safety": safety, "pub": pub, "sched": sched, "tg": tg,
        "link": link, "tail": tail, "sync": sync,
    }


def test_e2e_long_to_thematic(env):
    db, clock, postiz, _pub, sched, sync = (
        env["db"], env["clock"], env["postiz"], env["pub"], env["sched"], env["sync"]
    )
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, vertical_path, "
        "title_text, description_text, created_at) VALUES "
        "('videomaker', '/series_e2e', 'E2E', '/series_e2e/w.mp4', '/series_e2e/v.mp4', "
        "'Title', 'Desc', ?)",
        (now,),
    )
    n = sched.schedule_long_videos()
    assert n >= 1
    row = db.fetchone(
        "SELECT * FROM entity_platform_status WHERE entity_type='long_video' AND platform='youtube'"
    )
    assert row["status"] == "scheduled"
    pid = row["postiz_post_id"]
    # simulate publish + url
    postiz.mark_published(pid, "https://youtu.be/e2e")
    sync.sync()
    row2 = db.fetchone(
        "SELECT status, release_url FROM entity_platform_status "
        "WHERE entity_type='long_video' AND platform='youtube'"
    )
    assert row2["status"] == "published"
    assert "youtu.be" in (row2["release_url"] or "")
    # add shorts and schedule thematic
    vid = row["entity_id"]
    for i in range(2):
        db.execute(
            "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, "
            "video_path, title_text, description_text, created_at) "
            "VALUES ('videomaker', ?, ?, ?, ?, ?, ?, ?)",
            (vid, f"/series_e2e/shorts/s{i}", i, f"/series_e2e/shorts/s{i}/v.mp4",
             f"S{i}", f"Body{i}", now),
        )
    nt = sched.schedule_thematic_shorts(vid, "youtube")
    assert nt >= 1
    shorts = db.fetchall(
        "SELECT * FROM entity_platform_status WHERE entity_type='short' AND platform='youtube'"
    )
    assert len(shorts) >= 1


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
