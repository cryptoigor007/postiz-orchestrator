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
from orchestrator.webapp_api import WebAppAPI, validate_init_data, WEBAPP_DIR


def test_webapp_static_exists():
    assert (WEBAPP_DIR / "index.html").is_file()
    assert (WEBAPP_DIR / "app.js").is_file()
    assert (WEBAPP_DIR / "styles.css").is_file()


def test_dev_init_data():
    os.environ["WEBAPP_DEV"] = "1"
    assert validate_init_data("dev", "token") is not None
    assert validate_init_data("bad", "") is None


def test_api_status(tmp_path):
    os.environ["WEBAPP_DEV"] = "1"
    db = Database(tmp_path / "w.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, postiz, clock, tg)
    comps = {
        "cfg": cfg, "db": db, "clock": clock, "safety": safety,
        "scheduler": sched, "link_upd": link, "publisher": pub,
    }
    api = WebAppAPI(comps)
    code, payload, _ = api.handle(
        "GET", "/webapp/api/status",
        {"X-Telegram-Init-Data": "dev"}, b"",
    )
    assert code == 200
    assert "platforms" in payload
    code2, body, ctype = api.handle("GET", "/webapp/index.html", {}, b"")
    assert code2 == 200
    assert b"Orchestrator" in body
