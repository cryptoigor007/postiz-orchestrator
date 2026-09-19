from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.link_updater import LinkUpdater
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.telegram_bot import TelegramNotifier
from orchestrator.webapp_api import WebAppAPI, validate_init_data


def _make_init_data(bot_token: str, user_id: int = 42) -> str:
    user = json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":"))
    fields = {
        "auth_date": "1700000000",
        "query_id": "AAH",
        "user": user,
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@pytest.fixture
def env(tmp_path):
    os.environ["WEBAPP_DEV"] = "1"
    db = Database(tmp_path / "wa.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
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
    return WebAppAPI(comps), db, clock, cfg


def test_hmac_valid_and_invalid():
    token = "123456:ABC-DEF"
    good = _make_init_data(token)
    assert validate_init_data(good, token) is not None
    assert validate_init_data(good + "x", token) is None
    assert validate_init_data(good, "wrong") is None


def test_api_queue_calendar_pause(env):
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) VALUES ('v','/q','t',?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, postiz_scheduled_for) "
        "VALUES ('long_video', ?, 'youtube', 'scheduled', ?)",
        (vid, now),
    )
    code, payload, _ = api.handle("GET", "/webapp/api/queue", headers, b"")
    assert code == 200
    assert payload["items"]
    code, payload, _ = api.handle("GET", "/webapp/api/calendar", headers, b"")
    assert code == 200
    assert "days" in payload
    code, payload, _ = api.handle("POST", "/webapp/api/pause", headers, b"{}")
    assert code == 200
    st = db.fetchone("SELECT is_paused FROM platform_safety_state WHERE platform='youtube'")
    assert st["is_paused"] == 1


def test_api_force_link_and_metrics(env):
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) VALUES ('v','/fl2','t',?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/fl2'")["id"]
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status) "
        "VALUES ('long_video', ?, 'youtube', 'published')",
        (vid,),
    )
    body = json.dumps({
        "entity_id": vid,
        "platform": "youtube",
        "url": "https://youtu.be/polished",
    }).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/force_link", headers, body)
    assert code == 200
    code, payload, _ = api.handle("GET", "/webapp/api/metrics", headers, b"")
    assert code == 200


def test_unauthorized_without_init(env):
    api, db, clock, cfg = env
    os.environ.pop("WEBAPP_DEV", None)
    # without dev and without valid init
    code, payload, _ = api.handle("GET", "/webapp/api/status", {}, b"")
    assert code == 401
    os.environ["WEBAPP_DEV"] = "1"
