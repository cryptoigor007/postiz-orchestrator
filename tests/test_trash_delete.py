"""Удаление и корзина (Фаза 1–2 аудита→фичи): направление каскада, план, restore/purge."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

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
from orchestrator.watcher import Watcher
from orchestrator.webapp_api import WebAppAPI

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-Telegram-Init-Data": "dev"}


@pytest.fixture
def env(tmp_path):
    os.environ["WEBAPP_DEV"] = "1"
    db = Database(tmp_path / "tr.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, postiz, clock, tg)
    watcher = Watcher(db, cfg, clock, [])
    comps = {"cfg": cfg, "db": db, "clock": clock, "safety": safety,
             "scheduler": sched, "link_upd": link, "publisher": pub,
             "watcher": watcher, "postiz": postiz}
    return WebAppAPI(comps), db, clock, cfg


def _film(db, clock) -> int:
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) "
        "VALUES ('v', '/f', 'F', ?)", (clock.now().isoformat(),))
    return int(db.fetchone("SELECT id FROM long_videos ORDER BY id DESC")["id"])


def _short(db, clock, parent: int) -> int:
    db.execute(
        "INSERT INTO shorts (source, parent_video_id, folder_path, video_path, created_at) "
        "VALUES ('v', ?, '/f/shorts/s1', '/f/shorts/s1.mp4', ?)",
        (parent, clock.now().isoformat()))
    return int(db.fetchone("SELECT id FROM shorts ORDER BY id DESC")["id"])


def _row(db, et, ei, p):
    return db.fetchone(
        "SELECT status, deleted_at, cascade_from FROM entity_platform_status "
        "WHERE entity_type=? AND entity_id=? AND platform=?", (et, ei, p))


def _remove(api, body: dict):
    return api.handle("POST", "/webapp/api/queue/remove", HEADERS,
                      json.dumps(body).encode())


def test_telegram_trigger_keeps_youtube_by_default(env):
    api, db, clock, cfg = env
    fid = _film(db, clock)
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
               "VALUES ('long_video', ?, 'youtube', 'scheduled')", (fid,))
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
               "VALUES ('long_video', ?, 'telegram', 'scheduled')", (fid,))
    code, payload, _ = _remove(api, {"entity_type": "long_video", "entity_id": fid,
                                     "platform": "telegram"})
    assert code == 200 and payload["removed"] == 1
    assert _row(db, "long_video", fid, "telegram")["status"] == "skipped"
    assert _row(db, "long_video", fid, "youtube")["status"] == "scheduled"


def test_telegram_trigger_also_youtube(env):
    api, db, clock, cfg = env
    fid = _film(db, clock)
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
               "VALUES ('long_video', ?, 'youtube', 'scheduled')", (fid,))
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
               "VALUES ('long_video', ?, 'telegram', 'scheduled')", (fid,))
    code, payload, _ = _remove(api, {"entity_type": "long_video", "entity_id": fid,
                                     "platform": "telegram", "also_youtube": True})
    assert code == 200 and payload["removed"] == 2
    assert _row(db, "long_video", fid, "telegram")["status"] == "skipped"
    assert _row(db, "long_video", fid, "youtube")["status"] == "skipped"


def test_plan_only_reports_targets_and_changes_nothing(env):
    api, db, clock, cfg = env
    fid = _film(db, clock)
    sid = _short(db, clock, fid)
    for et, ei, p in (("long_video", fid, "youtube"), ("long_video", fid, "telegram"),
                      ("short", sid, "youtube")):
        db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
                   "VALUES (?, ?, ?, 'scheduled')", (et, ei, p))
    code, payload, _ = _remove(api, {"entity_type": "long_video", "entity_id": fid,
                                     "with_shorts": True, "plan_only": True})
    assert code == 200 and payload["plan_only"] is True
    assert payload["count"] == 3
    keys = {(t["entity_type"], t["platform"]) for t in payload["targets"]}
    assert keys == {("long_video", "youtube"), ("long_video", "telegram"), ("short", "youtube")}
    # ничего не изменилось
    assert _row(db, "long_video", fid, "youtube")["status"] == "scheduled"
    assert _row(db, "short", sid, "youtube")["status"] == "scheduled"


def test_published_blocks_delete(env):
    api, db, clock, cfg = env
    fid = _film(db, clock)
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
               "VALUES ('long_video', ?, 'youtube', 'published')", (fid,))
    code, payload, _ = _remove(api, {"entity_type": "long_video", "entity_id": fid,
                                     "platform": "youtube"})
    assert code == 200 and payload["removed"] == 0 and payload["blocked"]
    assert _row(db, "long_video", fid, "youtube")["status"] == "published"


def test_trash_list_restore_selected_and_all(env):
    api, db, clock, cfg = env
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
               "deleted_at, deleted_reason) VALUES "
               "('short', 1, 'youtube', 'skipped', '2026-03-10T12:00:00+00:00', 'platform')")
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
               "deleted_at, deleted_reason) VALUES "
               "('short', 2, 'telegram', 'skipped', '2026-03-10T12:01:00+00:00', 'platform')")
    code, payload, _ = api.handle("GET", "/webapp/api/trash", HEADERS, b"")
    assert code == 200 and payload["total"] == 2
    code, payload, _ = api.handle("POST", "/webapp/api/trash/restore", HEADERS,
                                  json.dumps({"ids": ["short|1|youtube"]}).encode())
    assert code == 200 and payload["restored"] == 1
    assert _row(db, "short", 1, "youtube")["status"] == "ready"
    assert _row(db, "short", 2, "telegram")["status"] == "skipped"
    code, payload, _ = api.handle("POST", "/webapp/api/trash/restore", HEADERS,
                                  json.dumps({"all": True}).encode())
    assert code == 200 and payload["restored"] == 1
    assert _row(db, "short", 2, "telegram")["status"] == "ready"


def test_trash_purge_removes_rows(env):
    api, db, clock, cfg = env
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
               "deleted_at) VALUES ('short', 5, 'youtube', 'skipped', "
               "'2026-03-10T12:00:00+00:00')")
    code, payload, _ = api.handle("POST", "/webapp/api/trash/purge", HEADERS,
                                  json.dumps({"all": True}).encode())
    assert code == 200 and payload["purged"] == 1
    assert _row(db, "short", 5, "youtube") is None


def test_cascade_flag_only_on_telegram(env):
    """F3: пометку «снято за YouTube» получает только Telegram, не инициатор."""
    api, db, clock, cfg = env
    fid = _film(db, clock)
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
               "VALUES ('long_video', ?, 'youtube', 'scheduled')", (fid,))
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
               "VALUES ('long_video', ?, 'telegram', 'scheduled')", (fid,))
    code, payload, _ = _remove(api, {"entity_type": "long_video", "entity_id": fid,
                                     "platform": "youtube"})
    assert code == 200 and payload["cascade"] == ["telegram"]
    assert (_row(db, "long_video", fid, "youtube")["cascade_from"] or "") == ""
    assert _row(db, "long_video", fid, "telegram")["cascade_from"] == "youtube"


def test_trash_counts_only_real_changes(env):
    """F4: restored/purged считают rowcount, а не итерации."""
    api, db, clock, cfg = env
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
               "deleted_at) VALUES ('short', 5, 'youtube', 'skipped', "
               "'2026-03-10T12:00:00+00:00')")
    code, p1, _ = api.handle("POST", "/webapp/api/trash/purge", HEADERS,
                             json.dumps({"ids": ["short|5|youtube"]}).encode())
    assert code == 200 and p1["purged"] == 1
    code, p2, _ = api.handle("POST", "/webapp/api/trash/purge", HEADERS,
                             json.dumps({"ids": ["short|5|youtube"]}).encode())
    assert code == 200 and p2["purged"] == 0
    code, p3, _ = api.handle("POST", "/webapp/api/trash/restore", HEADERS,
                             json.dumps({"ids": ["long_video|999|youtube"]}).encode())
    assert code == 200 and p3["restored"] == 0


def test_queue_title_localized_by_lang(env):
    """F6c: серверный префикс сущности локализуется по ?lang=."""
    api, db, clock, cfg = env
    db.execute("INSERT INTO long_videos (source, folder_path, title, created_at) "
               "VALUES ('v', '/l', 'Мой фильм', ?)", (clock.now().isoformat(),))
    vid = int(db.fetchone("SELECT id FROM long_videos ORDER BY id DESC")["id"])
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
               "postiz_scheduled_for) VALUES ('long_video', ?, 'youtube', 'scheduled', "
               "'2026-10-20T13:00:00+00:00')", (vid,))
    code, ru, _ = api.handle("GET", "/webapp/api/queue", HEADERS, b"")
    assert ru["items"][0]["title"] == "Фильм: Мой фильм"
    code, en, _ = api.handle("GET", "/webapp/api/queue?lang=en", HEADERS, b"")
    assert en["items"][0]["title"] == "Film: Мой фильм"
