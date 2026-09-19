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


def test_watcher_parses_meta(env):
    db, cfg, clock, root, series = env
    (series / "info_metadata.txt").write_text(
        "series: my_series\n"
        "package_title: НАСТОЯЩИЙ ЗАГОЛОВОК\n"
        "package_hook: hook line\n"
        "package_hashtags: #tag1 #tag2\n",
        encoding="utf-8",
    )
    (series / "vertical" / "my_series_description.txt").write_text(
        "Настоящее описание", encoding="utf-8"
    )
    short = series / "shorts" / "short_001"
    (short / "short_001_title.txt").write_text("Куда пропали друзья?", encoding="utf-8")
    (short / "short_001_description.txt").write_text("Описание шортса", encoding="utf-8")
    (short / "short_001_hashtags.txt").write_text("#shorts #test", encoding="utf-8")
    (short / "short_001_hook.txt").write_text("Хук!", encoding="utf-8")
    (short / "short_001_upload.txt").write_text("upload info", encoding="utf-8")
    (short / "short_001_cover.jpg").write_bytes(b"jpg")
    w = Watcher(db, cfg, clock, [str(root)])
    for _ in range(4):
        w.scan()
    lv = db.fetchone("SELECT * FROM long_videos")
    assert lv["title_text"] == "НАСТОЯЩИЙ ЗАГОЛОВОК"
    assert lv["description_text"] == "Настоящее описание"
    assert lv["hashtags_text"] == "#tag1 #tag2"
    s = db.fetchone("SELECT * FROM shorts")
    assert s["title_text"] == "Куда пропали друзья?"
    assert s["description_text"] == "Описание шортса"
    assert s["hashtags_text"] == "#shorts #test"
    assert s["hook_text"] == "Хук!"
    assert s["upload_text"] == "upload info"
    assert s["cover_path"].endswith("short_001_cover.jpg")


def test_watcher_root_can_be_series(env):
    db, cfg, clock, root, series = env
    w = Watcher(db, cfg, clock, [str(series)])
    for _ in range(4):
        w.scan()
    lv = db.fetchone("SELECT * FROM long_videos")
    assert lv is not None
    shorts = db.fetchall("SELECT * FROM shorts")
    assert len(shorts) >= 1
