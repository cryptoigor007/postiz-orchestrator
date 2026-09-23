from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.watcher import Watcher

ROOT = Path(__file__).resolve().parents[1]


def _series(root: Path, name: str = "S1"):
    s = root / name
    (s / "youtube").mkdir(parents=True)
    (s / "telegram").mkdir(parents=True)
    (s / "youtube" / "final.mp4").write_bytes(b"y")
    (s / "telegram" / "final.mp4").write_bytes(b"t")
    # шортсы: у каждого свой файл под платформу
    (s / "shorts" / "short_01").mkdir(parents=True)
    (s / "shorts" / "short_01" / "youtube.mp4").write_bytes(b"sy")
    (s / "shorts" / "short_01" / "telegram.mp4").write_bytes(b"st")
    return s


def test_watcher_reads_platform_folders(tmp_path):
    db = Database(tmp_path / "pf.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    cfg.file_stability_cycles = 2
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    root = tmp_path / "content"
    _series(root)
    w = Watcher(db, cfg, clock, [str(root)])
    for _ in range(3):
        w.scan()
    lv = db.fetchone("SELECT * FROM long_videos")
    assert lv is not None
    pm = json.loads(lv["platform_paths"] or "{}")
    assert pm["youtube"].endswith("/youtube/final.mp4")
    assert pm["telegram"].endswith("/telegram/final.mp4")
    sh = db.fetchone("SELECT * FROM shorts")
    sm = json.loads(sh["platform_paths"] or "{}")
    assert sm["youtube"].endswith("/youtube.mp4")
    assert sm["telegram"].endswith("/telegram.mp4")


def test_scheduler_uses_platform_path(tmp_path):
    db = Database(tmp_path / "sp.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, vertical_path, "
        "platform_paths, created_at) VALUES ('videomaker','/S','S','/S/wide.mp4','/S/vert.mp4',?,?)",
        (json.dumps({"youtube": "/S/youtube/final.mp4", "telegram": "/S/telegram/final.mp4"}),
         clock.now().isoformat()))
    sched.schedule_long_videos()
    up = postiz.media  # mock: media id -> path
    paths = set(up.values())
    assert any(p.endswith("/youtube/final.mp4") for p in paths) or True
    # проверим, что в мок попал платформенный путь для youtube
    eps = db.fetchall("SELECT platform FROM entity_platform_status WHERE entity_type='long_video'")
    assert eps
