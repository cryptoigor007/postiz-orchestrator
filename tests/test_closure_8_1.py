"""8.1.0 residual closure tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.media import _SIZE_CACHE, _cached_size
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.webapp_api import WEBAPP_BUILD

ROOT = Path(__file__).resolve().parents[1]


def test_webapp_build_id():
    assert WEBAPP_BUILD == "812"


def test_cached_size(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x" * 100)
    s1 = _cached_size(str(f))
    s2 = _cached_size(str(f))
    assert s1 == s2 == 100
    assert str(f) in _SIZE_CACHE


def test_posts_today_resets_on_new_day(tmp_path):
    db = Database(str(tmp_path / "t.sqlite"))
    cfg = load_config(ROOT / "config.yaml")
    clock = FakeClock(datetime(2026, 6, 15, 12, 0, tzinfo=UTC))
    safety = SafetyChecker(db, cfg, clock)
    platform = next(iter(cfg.platforms))
    db.execute(
        "INSERT INTO platform_safety_state (platform, posts_today, posts_today_date, updated_at) "
        "VALUES (?, 5, ?, ?)",
        (platform, "2026-06-14", clock.now().isoformat()),
    )
    safety.record_post(platform, clock.now())
    row = db.fetchone(
        "SELECT posts_today, posts_today_date FROM platform_safety_state WHERE platform=?",
        (platform,),
    )
    assert row["posts_today"] == 1
    # same day increments
    safety.record_post(platform, clock.now() + timedelta(hours=1))
    row = db.fetchone(
        "SELECT posts_today FROM platform_safety_state WHERE platform=?",
        (platform,),
    )
    assert row["posts_today"] == 2


def test_create_fail_releases_publishing(tmp_path):
    """Reserve must not leave rows stuck in publishing after create failure."""
    db = Database(str(tmp_path / "t.sqlite"))
    cfg = load_config(ROOT / "config.yaml")
    clock = FakeClock(datetime(2026, 6, 15, 12, 0, tzinfo=UTC))
    safety = SafetyChecker(db, cfg, clock)
    client = MockPostizClient()
    client.fail_create = True
    pub = Publisher(db, cfg, client, safety, clock, dry_run=False)
    platform = next(iter(cfg.platforms))
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title_text, created_at) "
        "VALUES ('test', '/x', 't', ?)",
        (clock.now().isoformat(),),
    )
    try:
        pub.publish(
            "long_video", 1, platform,
            media_path=None, content={"title": "t"},
            scheduled_for=clock.now() + timedelta(hours=3),
        )
    except Exception:
        pass
    row = db.fetchone(
        "SELECT status FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=1 AND platform=?",
        (platform,),
    )
    if row:
        assert row["status"] != "publishing"

