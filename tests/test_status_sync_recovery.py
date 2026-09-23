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
from orchestrator.status_sync import StatusSync


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "ss.sqlite")
    db.ensure_platform_states(["youtube"])
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    return db, cfg, clock, postiz


def _row(db):
    return db.fetchone(
        "SELECT status, last_error FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=1 AND platform='youtube'"
    )


def test_missing_streak_resets_when_post_found(env):
    """P1-4: успешный get_post сбрасывает ложный счётчик «пропал в Postiz»."""
    db, cfg, clock, postiz = env
    post = postiz.create_post("youtube", None, {"title": "t"},
                              datetime(2026, 3, 11, 16, 0, tzinfo=UTC))
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_post_id, postiz_scheduled_for, last_error) VALUES "
        "('long_video', 1, 'youtube', 'scheduled', ?, ?, 'missing_in_postiz:2')",
        (post.id, "2026-03-11T16:00:00+00:00"),
    )
    StatusSync(db, postiz, clock, cfg).sync()
    row = _row(db)
    assert row["last_error"] is None
    assert row["status"] == "scheduled"


def test_error_row_with_pid_recovers(env):
    """P1-4: строка error с живым postiz_post_id снова синхронизируется и лечится."""
    db, cfg, clock, postiz = env
    post = postiz.create_post("youtube", None, {"title": "t"},
                              datetime(2026, 3, 11, 16, 0, tzinfo=UTC))
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_post_id, postiz_scheduled_for, last_error) VALUES "
        "('long_video', 1, 'youtube', 'error', ?, ?, 'reconciliation_missing')",
        (post.id, "2026-03-11T16:00:00+00:00"),
    )
    StatusSync(db, postiz, clock, cfg).sync()
    row = _row(db)
    assert row["status"] == "scheduled"
    assert row["last_error"] is None
