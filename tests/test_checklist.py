from __future__ import annotations
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.postiz import MockPostizClient, PostizPost
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.status_sync import StatusSync
from orchestrator.link_updater import LinkUpdater
from orchestrator.telegram_bot import TelegramNotifier, setup_commands
from orchestrator.postiz_factory import create_postiz_client


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "c.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, postiz, clock, tg)
    sync = StatusSync(db, postiz, clock, cfg)
    comps = {
        "db": db, "cfg": cfg, "safety": safety, "scheduler": sched,
        "clock": clock, "link_upd": link, "publisher": pub,
    }
    setup_commands(tg, comps)
    return db, cfg, clock, postiz, safety, pub, sched, tg, link, sync


def test_factory_mock():
    c = create_postiz_client(dry_run=True)
    assert isinstance(c, MockPostizClient)


def test_auth_error_pauses(env):
    db, cfg, clock, postiz, safety, pub, sched, tg, link, sync = env
    safety.handle_error("youtube", "401 unauthorized token expired")
    assert safety.is_platform_paused("youtube")


def test_sync_scheduled_to_published(env):
    db, cfg, clock, postiz, safety, pub, sched, tg, link, sync = env
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v','/z','t','/z/w.mp4',?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    postiz.posts["px1"] = PostizPost(
        id="px1", platform="youtube",
        scheduled_for=clock.now(), status="published",
        release_url="https://youtu.be/xyz",
    )
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, postiz_post_id, postiz_scheduled_for) "
        "VALUES ('long_video', ?, 'youtube', 'scheduled', 'px1', ?)",
        (vid, now),
    )
    n = sync.sync()
    assert n >= 1
    row = db.fetchone(
        "SELECT status, release_url FROM entity_platform_status "
        "WHERE entity_id=? AND platform='youtube'",
        (vid,),
    )
    assert row["status"] == "published"
    assert row["release_url"] == "https://youtu.be/xyz"


def test_refresh_thematic_with_url(env):
    db, cfg, clock, postiz, safety, pub, sched, tg, link, sync = env
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v','/y','t','/y/w.mp4',?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    pub_time = datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc)
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, postiz_post_id, "
        "postiz_scheduled_for, published_at, release_url) "
        "VALUES ('long_video', ?, 'youtube', 'published', 'lp1', ?, ?, ?)",
        (vid, pub_time.isoformat(), pub_time.isoformat(), "https://youtu.be/abc"),
    )
    db.execute(
        "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, "
        "video_path, title_text, description_text, created_at) "
        "VALUES ('videomaker', ?, '/y/shorts/s0', 0, '/y/shorts/s0/v.mp4', 'S', 'Body', ?)",
        (vid, now),
    )
    sid = db.fetchone("SELECT id FROM shorts")["id"]
    # pre-create scheduled short without link in description
    postiz.posts["old1"] = PostizPost(
        id="old1", platform="youtube",
        scheduled_for=pub_time + timedelta(hours=4), status="scheduled",
        content={"description": "Body"},
    )
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, postiz_post_id, postiz_scheduled_for) "
        "VALUES ('short', ?, 'youtube', 'scheduled', 'old1', ?)",
        (sid, (pub_time + timedelta(hours=4)).isoformat()),
    )
    n = link.refresh_thematic_after_url(vid, "youtube", sched)
    assert n >= 1
    # old should be deleted from postiz
    assert "old1" not in postiz.posts or any(
        p.content and "youtu.be" in str(p.content.get("description", ""))
        for p in postiz.posts.values()
    )


def test_tg_status_command(env):
    db, cfg, clock, postiz, safety, pub, sched, tg, link, sync = env
    resp = tg.handle_update(7004751908, "/status")
    assert resp is not None
    assert "Status" in resp or "No entities" in resp or "entities" in resp.lower() or "youtube" in resp.lower() or resp == "No entities"


def test_schema_indexes(env):
    db, cfg, clock, postiz, safety, pub, sched, tg, link, sync = env
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )
    names = {r["name"] for r in rows}
    assert "idx_eps_platform_sched" in names
