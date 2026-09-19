from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker


@pytest.fixture
def setup(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    db.ensure_platform_states(["youtube"])
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    return db, cfg, clock, postiz, safety, pub


def test_idempotent_create(setup):
    db, cfg, clock, postiz, safety, pub = setup
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/a', 't', '/a/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    sched = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    content = {"title": "T", "description": "D"}

    p1 = pub.publish("long_video", vid, "youtube", "/a/w.mp4", content, sched)
    assert p1 is not None
    assert p1.id.startswith("post_")

    p2 = pub.publish("long_video", vid, "youtube", "/a/w.mp4", content, sched)
    assert p2 is not None
    assert p2.id == p1.id  # same post, no duplicate
    assert len(postiz.posts) == 1


def test_safety_blocks(setup):
    db, cfg, clock, postiz, safety, pub = setup
    safety.pause_platform("youtube", "test")
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/b', 't', '/b/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/b'")["id"]
    sched = datetime(2026, 3, 11, 16, 0, tzinfo=UTC)
    p = pub.publish("long_video", vid, "youtube", "/b/w.mp4", {"title": "x"}, sched)
    assert p is None


def test_dry_run(setup):
    db, cfg, clock, postiz, safety, _ = setup
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=True)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/c', 't', '/c/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/c'")["id"]
    p = pub.publish(
        "long_video", vid, "youtube", "/c/w.mp4", {"title": "x"},
        datetime(2026, 3, 12, 16, 0, tzinfo=UTC),
    )
    assert p is None
    assert len(postiz.posts) == 0


def test_hourly_create_limit(setup):
    db, cfg, clock, postiz, safety, pub = setup
    cfg.limits.postiz_create_per_hour = 1
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/hl', 't', '/hl/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/hl'")["id"]
    sched = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    p1 = pub.publish("long_video", vid, "youtube", "/hl/w.mp4", {"title": "x"}, sched)
    assert p1 is not None
    vid2 = None
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/hl2', 't', '/hl2/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid2 = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/hl2'")["id"]
    p2 = pub.publish("long_video", vid2, "youtube", "/hl2/w.mp4", {"title": "y"},
                     datetime(2026, 3, 11, 16, 0, tzinfo=UTC))
    assert p2 is None  # hourly limit hit
