from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.link_updater import LinkUpdater
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.status_sync import Reconciliation, StatusSync
from orchestrator.telegram_bot import TelegramNotifier
from orchestrator.watcher import Watcher
from orchestrator.webapp_api import WebAppAPI

ROOT = Path(__file__).resolve().parents[1]


def env(tmp_path):
    os.environ["WEBAPP_DEV"] = "1"
    os.environ["WEBAPP_BROWSE_ROOT"] = str(tmp_path)
    db = Database(tmp_path / "act.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 9, 19, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, postiz, clock, tg)
    sync = StatusSync(db, postiz, clock, cfg)
    recon = Reconciliation(db, postiz, clock)
    comps = {"cfg": cfg, "db": db, "clock": clock, "safety": safety,
             "scheduler": sched, "link_upd": link, "publisher": pub,
             "watcher": Watcher(db, cfg, clock, []), "status_sync": sync, "recon": recon}
    return WebAppAPI(comps), db


def test_sync_reconcile_backup_schedule_pause(tmp_path):
    api, db = env(tmp_path)
    h = {"X-Telegram-Init-Data": "dev"}
    assert api.handle("POST", "/webapp/api/sync", h, b"{}")[0] == 200
    assert api.handle("POST", "/webapp/api/reconcile", h, b"{}")[0] == 200
    code, payload, _ = api.handle("POST", "/webapp/api/backup", h, b"{}")
    assert code == 200 and payload["path"]
    assert api.handle("POST", "/webapp/api/schedule", h, b"{}")[0] == 200
    code, payload, _ = api.handle("POST", "/webapp/api/pause_platform", h,
                                  json.dumps({"platform": "youtube"}).encode())
    assert code == 200
    st = db.fetchone("SELECT is_paused FROM platform_safety_state WHERE platform='youtube'")
    assert st["is_paused"] == 1
