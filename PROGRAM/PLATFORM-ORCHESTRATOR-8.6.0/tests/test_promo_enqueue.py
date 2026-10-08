"""KIND-01 scheduler promo auto-enqueue for content_kind_default=promo*."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from orchestrator.db import Database
from orchestrator.scheduler import Scheduler


def test_enqueue_promo_creates_ready_rows(tmp_path: Path):
    db = Database(str(tmp_path / "p.sqlite"))
    db.execute(
        "INSERT INTO long_videos (id, folder_path, source, created_at) "
        "VALUES (1, '/x', 'videomaker', '2026-01-01')"
    )
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
        "VALUES ('long_video', 1, 'youtube', 'published')"
    )
    cfg = MagicMock()
    x = MagicMock()
    x.enabled = True
    x.content_kind_default = "promo_text"
    x.account_id = "x-acc"
    cfg.platforms = {
        "x": x,
        "youtube": MagicMock(enabled=True, content_kind_default="video_native", account_id="yt-acc"),
    }
    cfg.link_update = MagicMock(release_url_timeout_min=90)
    cfg.safety = MagicMock(jitter_seconds=0)
    clock = MagicMock()
    clock.now.return_value = datetime(2026, 1, 2, tzinfo=timezone.utc)
    sch = Scheduler(db, cfg, MagicMock(), MagicMock(), clock)
    n = sch._enqueue_promo_for_long()
    assert n >= 1
    row = db.fetchone(
        "SELECT status, content_kind, source FROM entity_platform_status "
        "WHERE platform='x' AND entity_id=1 AND account_id='x-acc'"
    )
    assert row is not None
    assert row["status"] == "ready"
    assert row["content_kind"] == "promo_text"


def test_enqueue_promo_does_not_mix_accounts(tmp_path: Path):
    db = Database(str(tmp_path / "p.sqlite"))
    db.execute(
        "INSERT INTO long_videos (id, folder_path, source, created_at) "
        "VALUES (1, '/x', 'videomaker', '2026-01-01')"
    )
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, account_id, status) "
        "VALUES ('long_video', 1, 'youtube', 'yt-acc', 'published')"
    )
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, account_id, status) "
        "VALUES ('long_video', 1, 'x', 'other-x', 'published')"
    )
    cfg = MagicMock()
    cfg.platforms = {
        "x": MagicMock(enabled=True, content_kind_default="promo_text", account_id="x-acc"),
        "youtube": MagicMock(enabled=True, content_kind_default="video_native", account_id="yt-acc"),
    }
    cfg.link_update = MagicMock(release_url_timeout_min=90)
    cfg.safety = MagicMock(jitter_seconds=0)
    clock = MagicMock()
    clock.now.return_value = datetime(2026, 1, 2, tzinfo=timezone.utc)
    sch = Scheduler(db, cfg, MagicMock(), MagicMock(), clock)
    assert sch._enqueue_promo_for_long() == 1
    rows = db.fetchall(
        "SELECT account_id, status FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=1 AND platform='x' ORDER BY account_id"
    )
    assert [(r['account_id'], r['status']) for r in rows] == [('other-x', 'published'), ('x-acc', 'ready')]
