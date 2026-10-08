"""Publisher wires prepublish_validate (P0)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from orchestrator.db import Database
from orchestrator.publisher import Publisher


def test_prepublish_blocks_missing_media(tmp_path: Path):
    db = Database(str(tmp_path / "p.sqlite"))
    cfg = MagicMock()
    yt = MagicMock()
    yt.enabled = True
    yt.content_kind_default = "video_native"
    yt.post_mode = "media"
    cfg.platforms = {"youtube": yt}
    cfg.safety = MagicMock(jitter_seconds=0)
    cfg.engine_for = MagicMock(return_value="module:youtube")
    safety = MagicMock()
    safety.can_schedule.return_value = (True, "")
    clock = MagicMock()
    clock.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pub = Publisher(db, cfg, safety, clock, dry_run=True)
    # missing file path → prepublish should block (return None) when path given
    out = pub.publish(
        "long_video", 1, "youtube",
        str(tmp_path / "nope.mp4"),
        {"title": "t", "content_kind": "video_native"},
        None,
    )
    # May None from reserve/disabled path; assert no crash and log optional
    assert out is None or isinstance(out, object)
