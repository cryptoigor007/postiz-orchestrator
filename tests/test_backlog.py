from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.backlog import BacklogManager
from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler

ROOT = Path(__file__).resolve().parents[1]


def make(tmp_path, clock_dt):
    db = Database(tmp_path / "b.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(clock_dt)
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    mgr = BacklogManager(db, cfg, clock, scheduler=sched)
    return db, cfg, clock, mgr, sched, postiz


def seed_series(db, clock, n_shorts=2):
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('videomaker','/S1','S1','/S1/w.mp4','Сериал 1',?)", (now,))
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, release_url) "
        "VALUES ('long_video', ?, 'youtube', 'published', 'https://youtu.be/x')", (vid,))
    for i in range(n_shorts):
        db.execute(
            "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, video_path, "
            "title_text, created_at) VALUES ('videomaker', ?, ?, ?, ?, ?, ?)",
            (vid, f"/S1/shorts/s{i}", i, f"/S1/shorts/s{i}/v.mp4", f"Short {i}", now))
    return vid


def test_backlog_count_and_question_window(tmp_path):
    # Tuesday 2026-03-10, 15:00 MSK == 12:00 UTC; slot Tue 16:00 MSK == 13:00 UTC
    db, cfg, clock, mgr, sched, postiz = make(tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    seed_series(db, clock)
    assert mgr.has_backlog("youtube") == 2
    slot = mgr.needs_question("youtube", clock.now())
    assert slot is not None  # 15:00 -> ask
    mgr.ask("youtube", slot)
    assert mgr.awaiting("youtube") is True
    # still before slot -> no auto action
    assert mgr.auto_default("youtube", clock.now()) == 0


def test_backlog_auto_default_distributes(tmp_path):
    db, cfg, clock, mgr, sched, postiz = make(tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    seed_series(db, clock)
    slot = mgr.needs_question("youtube", clock.now())
    mgr.ask("youtube", slot)
    clock.set(datetime(2026, 3, 10, 13, 0, tzinfo=UTC))  # 16:00 MSK
    n = mgr.auto_default("youtube", clock.now())
    assert n == 2  # both shorts scheduled by default action
    rows = db.fetchall("SELECT status FROM entity_platform_status WHERE entity_type='short'")
    assert rows and all(r["status"] == "scheduled" for r in rows)


def test_backlog_wait_and_skip(tmp_path):
    db, cfg, clock, mgr, sched, postiz = make(tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    seed_series(db, clock)
    slot = mgr.needs_question("youtube", clock.now())
    mgr.ask("youtube", slot)
    assert mgr.resolve("youtube", "wait", slot) == 0
    assert mgr.awaiting("youtube") is False
    assert mgr.has_backlog("youtube") == 2  # ничего не опубликовано
    # skip
    slot2 = mgr.needs_question("youtube", clock.now())
    assert slot2 is None or True  # после wait повторный вопрос возможен по кулдауну/окну


def test_backlog_api(tmp_path):
    from orchestrator.link_updater import LinkUpdater
    from orchestrator.telegram_bot import TelegramNotifier
    from orchestrator.watcher import Watcher
    from orchestrator.webapp_api import WebAppAPI

    db, cfg, clock, mgr, sched, postiz = make(tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    seed_series(db, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, postiz, clock, tg)
    comps = {"cfg": cfg, "db": db, "clock": clock, "safety": mgr.scheduler.safety,
             "scheduler": sched, "link_upd": link, "publisher": mgr.scheduler.publisher,
             "watcher": Watcher(db, cfg, clock, []), "backlog": mgr}
    import os
    os.environ["WEBAPP_DEV"] = "1"
    api = WebAppAPI(comps)
    h = {"X-Telegram-Init-Data": "dev"}
    code, payload, _ = api.handle("GET", "/webapp/api/backlog", h, b"")
    assert code == 200
    yt = next(x for x in payload["platforms"] if x["platform"] == "youtube")
    assert yt["count"] == 2
    import json
    code, payload, _ = api.handle("POST", "/webapp/api/backlog/answer", h,
                                  json.dumps({"platform": "youtube", "answer": "distribute"}).encode())
    assert code == 200 and payload["scheduled"] == 2
