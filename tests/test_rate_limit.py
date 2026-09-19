from __future__ import annotations
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.link_updater import LinkUpdater
from orchestrator.telegram_bot import TelegramNotifier
from orchestrator.watcher import Watcher
from orchestrator.webapp_api import WebAppAPI

ROOT = Path(__file__).resolve().parents[1]


def test_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_DEV", "1")
    monkeypatch.setenv("WEBAPP_RATE_LIMIT", "2")
    db = Database(tmp_path / "r.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, postiz, clock, tg)
    comps = {"cfg": cfg, "db": db, "clock": clock, "safety": safety,
             "scheduler": sched, "link_upd": link, "publisher": pub,
             "watcher": Watcher(db, cfg, clock, [])}
    api = WebAppAPI(comps)
    h = {"X-Telegram-Init-Data": "dev"}
    codes = [api.handle("GET", "/webapp/api/status", h, b"")[0] for _ in range(3)]
    assert codes[:2] == [200, 200]
    assert codes[2] == 429
