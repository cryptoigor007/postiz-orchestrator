from __future__ import annotations

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
from orchestrator.runner import Runner
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.status_sync import Reconciliation, StatusSync
from orchestrator.tail import TailManager
from orchestrator.telegram_bot import TelegramNotifier
from orchestrator.watcher import Watcher


def test_runner_builds(tmp_path):
    db = Database(tmp_path / "r.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    comps = {
        "cfg": cfg,
        "db": db,
        "clock": clock,
        "postiz": postiz,
        "safety": safety,
        "publisher": pub,
        "scheduler": sched,
        "status_sync": StatusSync(db, postiz, clock, cfg),
        "recon": Reconciliation(db, postiz, clock),
        "watcher": Watcher(db, cfg, clock, []),
        "tg": tg,
        "tail": TailManager(db, cfg, clock, tg),
        "link_upd": LinkUpdater(db, cfg, postiz, clock, tg),
    }
    r = Runner(comps, dry_run=True)
    r._stop = True  # don't loop
    r._cycle_watch()
    r._cycle_sync()
    r._cycle_recon()
    assert True
