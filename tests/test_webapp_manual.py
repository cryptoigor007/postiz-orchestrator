from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.manual_uploads import ManualUploadsService
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.link_updater import LinkUpdater
from orchestrator.telegram_bot import TelegramNotifier
from orchestrator.watcher import Watcher
from orchestrator.webapp_api import WebAppAPI

ROOT = Path(__file__).resolve().parents[1]


class FakeSource:
    def __init__(self, uploads):
        self.uploads = uploads
        self.deleted = []

    def list_uploads(self, params=None):
        return list(self.uploads)

    def delete(self, external_id):
        self.deleted.append(external_id)
        return True


def env(tmp_path):
    os.environ["WEBAPP_DEV"] = "1"
    os.environ["WEBAPP_BROWSE_ROOT"] = str(tmp_path)
    db = Database(tmp_path / "mw.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, postiz, clock, tg)
    watcher = Watcher(db, cfg, clock, [])
    manual = ManualUploadsService(db, cfg, clock)
    source = FakeSource([{"external_id": "V1", "title": "Серия 1",
                          "published_at": "2026-09-19T11:00:00+00:00"}])
    comps = {
        "cfg": cfg, "db": db, "clock": clock, "safety": safety,
        "scheduler": sched, "link_upd": link, "publisher": pub,
        "watcher": watcher, "postiz": postiz, "manual": manual,
        "manual_sources": {"youtube": source},
    }
    return WebAppAPI(comps), db, clock, cfg, source


def test_manual_scan_and_plan(tmp_path):
    api, db, clock, cfg, source = env(tmp_path)
    h = {"X-Telegram-Init-Data": "dev"}
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('videomaker','/s1','S1','/s1/w.mp4','Серия 1',?)", (now,))
    code, payload, _ = api.handle("POST", "/webapp/api/manual/scan", h, b"{}")
    assert code == 200
    assert payload["stats"]["youtube"]["found"] == 1
    code, payload, _ = api.handle("GET", "/webapp/api/manual/uploads", h, b"")
    assert code == 200
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["origin"] == "manual"
    assert item["match_status"] == "suggested"
    assert item["candidates"]
    code, plan, _ = api.handle("GET", "/webapp/api/manual/plan", h, b"")
    assert plan["total"] == 1 and plan["by_status"]["suggested"] == 1


def test_manual_confirm_and_claim_action(tmp_path):
    api, db, clock, cfg, source = env(tmp_path)
    h = {"X-Telegram-Init-Data": "dev"}
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('videomaker','/s2','S2','/s2/w.mp4','Серия 1',?)", (now,))
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/s2'")["id"]
    api.handle("POST", "/webapp/api/manual/scan", h, b"{}")
    up = db.list_uploads()[0]
    body = json.dumps({"entity_type": "long_video", "entity_id": vid}).encode()
    code, payload, _ = api.handle("POST", f"/webapp/api/manual/uploads/{up['id']}/confirm", h, body)
    assert code == 200 and payload["ok"] is True
    eps = db.fetchone(
        "SELECT status FROM entity_platform_status WHERE entity_type='long_video' "
        "AND entity_id=? AND platform='youtube'", (vid,))
    assert eps["status"] == "published"
    # claim-action delete calls engine.delete
    code, payload, _ = api.handle(
        "POST", f"/webapp/api/manual/uploads/{up['id']}/claim-action", h,
        json.dumps({"action": "delete"}).encode())
    assert code == 200
    assert source.deleted == ["V1"]
