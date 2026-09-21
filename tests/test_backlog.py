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
    # P1-5: решение по слоту зафиксировано — повторного вопроса в том же окне нет
    assert mgr.needs_question("youtube", clock.now()) is None


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


def test_schedule_backlog_from_date(tmp_path):
    db, cfg, clock, mgr, sched, postiz = make(tmp_path, datetime(2026, 3, 10, 14, 0, tzinfo=UTC))
    seed_series(db, clock)
    n = sched.schedule_backlog("youtube", start_date="2026-03-20")
    assert n == 2
    rows = db.fetchall(
        "SELECT postiz_scheduled_for FROM entity_platform_status "
        "WHERE entity_type='short' AND postiz_scheduled_for IS NOT NULL ORDER BY postiz_scheduled_for")
    assert rows
    assert all(r["postiz_scheduled_for"][:10] >= "2026-03-19" for r in rows)  # локальная дата >= 20.03 MSK


def test_transport_no_ack_dedupe():
    from orchestrator.telegram_transport import TelegramTransport
    tr = TelegramTransport(token="x", on_message=lambda c, t: None)
    tr.no_ack = True
    upd = {"update_id": 5, "message": {"chat": {"id": 1}, "text": "hi"}}
    assert tr._accept(upd) is True
    assert tr._accept(upd) is False  # дубликат не обрабатываем
    upd2 = {"update_id": 6, "message": {"chat": {"id": 1}, "text": "hi2"}}
    assert tr._accept(upd2) is True


def test_backlog_blocks_next_series(tmp_path):
    """Пока остаток не выложен, планировщик не ставит новое длинное видео на этой платформе."""
    db, cfg, clock, mgr, sched, postiz = make(tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    seed_series(db, clock)
    # новая серия готова (нет eps)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, vertical_path, created_at) "
        "VALUES ('videomaker','/S2','Сериал 2','/S2/w.mp4','/S2/v.mp4',?)",
        (clock.now().isoformat(),))
    # включаем режим распределения остатка
    db.execute("UPDATE platform_queue_state SET series_tail_mode=1 WHERE platform='youtube'")
    s2 = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/S2'")["id"]
    n = sched.schedule_long_videos()
    blocked = db.fetchone(
        "SELECT 1 FROM entity_platform_status WHERE entity_type='long_video' "
        "AND entity_id=? AND platform='youtube'", (s2,))
    assert blocked is None     # youtube заблокирован остатком
    assert n >= 0
    # telegram не в режиме остатка -> может планировать
    # распределяем остаток -> после опустошения режим снимается
    clock.set(datetime(2026, 3, 10, 13, 0, tzinfo=UTC))
    mgr.resolve("youtube", "distribute")
    st = db.fetchone("SELECT series_tail_mode FROM platform_queue_state WHERE platform='youtube'")
    assert st["series_tail_mode"] == 0
    n2 = sched.schedule_long_videos()
    now_row = db.fetchone(
        "SELECT 1 FROM entity_platform_status WHERE entity_type='long_video' "
        "AND entity_id=? AND platform='youtube'", (s2,))
    assert now_row                      # теперь новая серия планируется
    assert n2 >= 1


def test_question_even_if_new_episode_ready(tmp_path):
    db, cfg, clock, mgr, sched, postiz = make(tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    seed_series(db, clock)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('videomaker','/S2','Сериал 2','/S2/w.mp4',?)", (clock.now().isoformat(),))
    slot = mgr.needs_question("youtube", clock.now())
    assert slot is not None  # остаток важнее старта новой серии


def test_backlog_slots_use_effective_override(tmp_path):
    """P1-3: слоты бэклога строятся из effective-настроек, а не из сырого конфига."""
    import json
    from zoneinfo import ZoneInfo

    db, cfg, clock, mgr, sched, postiz = make(
        tmp_path, datetime(2026, 3, 15, 6, 0, tzinfo=UTC))  # Sunday
    db.set_setting("schedule_settings", json.dumps({
        "youtube": {"long": {"days": ["sun"], "time": "10:00"},
                    "standalone": {"days": ["sun"], "times": ["11:00"]},
                    "thematic": {"time": "12:00"}}}))
    slots = sched._backlog_slots("youtube")
    hhmm = {x.astimezone(ZoneInfo("Europe/Moscow")).strftime("%H:%M") for x in slots}
    assert {"10:00", "11:00", "12:00"} <= hhmm
    assert "16:00" not in hhmm and "20:30" not in hhmm


def test_schedule_backlog_with_override_places_shorts(tmp_path):
    """P1-3: при override раскладка остатка проходит (слоты канонические)."""
    import json

    db, cfg, clock, mgr, sched, postiz = make(
        tmp_path, datetime(2026, 3, 15, 6, 0, tzinfo=UTC))  # Sunday 09:00 MSK
    seed_series(db, clock, n_shorts=2)
    db.set_setting("schedule_settings", json.dumps({
        "youtube": {"long": {"days": ["sun"], "time": "10:00"},
                    "standalone": {"days": ["sun"], "times": ["11:00"]},
                    "thematic": {"time": "12:00"}}}))
    assert sched.schedule_backlog("youtube") == 2


def test_backlog_wait_is_recorded_and_not_reasked(tmp_path):
    """P1-5: wait сохраняется — вопрос не повторяется, дефолт не раскладывает остаток."""
    db, cfg, clock, mgr, sched, postiz = make(
        tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    seed_series(db, clock)
    slot = mgr.needs_question("youtube", clock.now())
    assert slot is not None
    mgr.ask("youtube", slot)
    assert mgr.resolve("youtube", "wait") == 0
    assert mgr.needs_question("youtube", clock.now()) is None
    clock.set(datetime(2026, 3, 10, 13, 0, tzinfo=UTC))  # слот настал
    assert mgr.auto_default("youtube", clock.now()) == 0
    assert mgr.has_backlog("youtube") == 2  # ничего не ушло
    # следующий слот по-прежнему спрашивает — фича не выключена
    assert mgr.needs_question("youtube", datetime(2026, 3, 13, 12, 0, tzinfo=UTC)) is not None


def test_backlog_schedule_no_upload_storm(tmp_path):
    """P1-6: раскладка остатка при ошибке create — одна попытка на шорт и кулдаун."""
    db, cfg, clock, mgr, sched, postiz = make(
        tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    seed_series(db, clock, n_shorts=2)
    postiz.fail_create = True
    sched.schedule_backlog("youtube")
    assert len(postiz._orphan_media) == 2  # по одной попытке на шорт
    sched.schedule_backlog("youtube")
    assert len(postiz._orphan_media) == 2  # кулдаун — новых нет
    clock.advance(minutes=31)
    sched.schedule_backlog("youtube")
    assert len(postiz._orphan_media) == 4
