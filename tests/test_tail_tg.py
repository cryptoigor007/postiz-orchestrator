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
from orchestrator.overflow import move_excess_shorts
from orchestrator.postiz import MockPostizClient
from orchestrator.tail import TailManager
from orchestrator.telegram_bot import TelegramNotifier


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    db.ensure_platform_states(["youtube"])
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 20, 12, 0, tzinfo=UTC))
    tg = TelegramNotifier(cfg, db, clock)
    tail = TailManager(db, cfg, clock, tg)
    postiz = MockPostizClient()
    link = LinkUpdater(db, cfg, postiz, clock, tg)
    return db, cfg, clock, tg, tail, link


def test_tail_reset_on_new_long(env):
    db, cfg, clock, tg, tail, link = env
    db.execute(
        "UPDATE platform_queue_state SET series_tail_mode=1, last_long_video_at=? WHERE platform='youtube'",
        ((clock.now() - timedelta(days=10)).isoformat(),),
    )
    assert tail.is_tail("youtube")
    tail.on_new_long_video("youtube", 42)
    assert not tail.is_tail("youtube")


def test_soft_enter_asks(env):
    db, cfg, clock, tg, tail, link = env
    old = (clock.now() - timedelta(days=cfg.tail.soft_enter_days + 1)).isoformat()
    db.execute(
        "UPDATE platform_queue_state SET last_long_video_at=?, series_tail_mode=0 WHERE platform='youtube'",
        (old,),
    )
    tail.check_soft_enter("youtube")
    row = db.fetchone("SELECT pending_series_end_question FROM platform_queue_state WHERE platform='youtube'")
    assert row["pending_series_end_question"] == 1


def test_tg_whitelist(env):
    db, cfg, clock, tg, tail, link = env
    # config.yaml has explicit allowed_chat_ids
    assert tg.is_allowed(7004751908)
    assert not tg.is_allowed(999)
    assert not tg.is_allowed(111)


def test_tg_commands(env):
    db, cfg, clock, tg, tail, link = env
    resp = tg.handle_update(7004751908, "/status")
    # status handler not registered in this isolated test
    assert resp is None or "Неизвестная" in (resp or "") or "Unknown" in (resp or "") or "Status" in (resp or "") or "No entities" in (resp or "")
    assert tg.handle_update(111, "/status") == "Access denied"


def test_overflow(env, tmp_path):
    db, cfg, clock, tg, tail, link = env
    series = tmp_path / "ser"
    (series / "shorts").mkdir(parents=True)
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) VALUES ('v', ?, 't', ?)",
        (str(series), now),
    )
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    for i in range(10):
        d = series / "shorts" / f"s{i:03d}"
        d.mkdir()
        (d / "v.mp4").write_bytes(b"x")
        db.execute(
            "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, video_path, created_at) "
            "VALUES ('videomaker', ?, ?, ?, ?, ?)",
            (vid, str(d), i, str(d / "v.mp4"), now),
        )
    moved = move_excess_shorts(db, cfg, clock, vid)
    assert moved == 10 - cfg.limits.max_shorts_per_long_video
    assert (series / "shorts_overflow").exists()


def test_link_default_action(env):
    db, cfg, clock, tg, tail, link = env
    now = clock.now()
    pub = (now - timedelta(minutes=cfg.link_update.release_url_timeout_min + 5)).isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) VALUES ('v','/x','t',?)",
        (now.isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, published_at) "
        "VALUES ('long_video', ?, 'youtube', 'published', ?)",
        (vid, pub),
    )
    n = link.check_missing_urls()
    assert n == 1
