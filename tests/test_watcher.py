from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.watcher import Watcher


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "w.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    root = tmp_path / "content"
    series = root / "my_series"
    (series / "wide").mkdir(parents=True)
    (series / "vertical").mkdir(parents=True)
    (series / "shorts" / "short_001").mkdir(parents=True)
    wide = series / "wide" / "final_16x9.mp4"
    wide.write_bytes(b"fake" * 100)
    vert = series / "vertical" / "final_9x16.mp4"
    vert.write_bytes(b"fake" * 100)
    short_v = series / "shorts" / "short_001" / "clip.mp4"
    short_v.write_bytes(b"short" * 50)
    (series / "info_metadata.txt").write_text("Title here")
    return db, cfg, clock, root, series


def test_watcher_registers(env):
    db, cfg, clock, root, series = env
    w = Watcher(db, cfg, clock, [str(root)])
    # need several scans for all files to become stable
    for _ in range(4):
        w.scan()
    row = db.fetchone("SELECT * FROM long_videos")
    assert row is not None
    assert "my_series" in row["folder_path"]
    shorts = db.fetchall("SELECT * FROM shorts")
    assert len(shorts) >= 1
