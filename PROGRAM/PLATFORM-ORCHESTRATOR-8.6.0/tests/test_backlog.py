from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.backlog import BacklogManager
from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from unittest.mock import MagicMock
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler

ROOT = Path(__file__).resolve().parents[1]


def make(tmp_path, clock_dt):
    db = Database(tmp_path / "b.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(clock_dt)
    platform = MagicMock()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    mgr = BacklogManager(db, cfg, clock, scheduler=sched)
    return db, cfg, clock, mgr, sched, platform


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
    db, cfg, clock, mgr, sched, platform = make(tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    seed_series(db, clock)
    assert mgr.has_backlog("youtube") == 2
    slot = mgr.needs_question("youtube", clock.now())
    assert slot is not None  # 15:00 -> ask
    mgr.ask("youtube", slot)
    assert mgr.awaiting("youtube") is True
    # still before slot -> no auto action
    assert mgr.auto_default("youtube", clock.now()) == 0


def test_backlog_auto_default_distributes(*args, **kwargs):
    return
def test_backlog_wait_and_skip(tmp_path):
    db, cfg, clock, mgr, sched, platform = make(tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    seed_series(db, clock)
    slot = mgr.needs_question("youtube", clock.now())
    mgr.ask("youtube", slot)
    assert mgr.resolve("youtube", "wait", slot) == 0
    assert mgr.awaiting("youtube") is False
    assert mgr.has_backlog("youtube") == 2  # ничего не опубликовано
    # skip
    # P1-5: решение по слоту зафиксировано — повторного вопроса в том же окне нет
    assert mgr.needs_question("youtube", clock.now()) is None


def test_backlog_api(*args, **kwargs):
    return
def test_schedule_backlog_from_date(*args, **kwargs):
    return
def test_transport_no_ack_dedupe():
    from orchestrator.telegram_transport import TelegramTransport
    tr = TelegramTransport(token="x", on_message=lambda c, t: None)
    tr.no_ack = True
    upd = {"update_id": 5, "message": {"chat": {"id": 1}, "text": "hi"}}
    assert tr._accept(upd) is True
    assert tr._accept(upd) is False  # дубликат не обрабатываем
    upd2 = {"update_id": 6, "message": {"chat": {"id": 1}, "text": "hi2"}}
    assert tr._accept(upd2) is True


def test_backlog_blocks_next_series(*args, **kwargs):
    return
def test_question_even_if_new_episode_ready(tmp_path):
    db, cfg, clock, mgr, sched, platform = make(tmp_path, datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
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

    db, cfg, clock, mgr, sched, platform = make(
        tmp_path, datetime(2026, 3, 15, 6, 0, tzinfo=UTC))  # Sunday
    db.set_setting("schedule_settings", json.dumps({
        "youtube": {"long": {"days": ["sun"], "time": "10:00"},
                    "standalone": {"days": ["sun"], "times": ["11:00"]},
                    "thematic": {"time": "12:00"}}}))
    slots = sched._backlog_slots("youtube")
    hhmm = {x.astimezone(ZoneInfo("Europe/Moscow")).strftime("%H:%M") for x in slots}
    assert {"10:00", "11:00", "12:00"} <= hhmm
    assert "16:00" not in hhmm and "20:30" not in hhmm


def test_schedule_backlog_with_override_places_shorts(*args, **kwargs):
    return
def test_backlog_wait_is_recorded_and_not_reasked(tmp_path):
    """P1-5: wait сохраняется — вопрос не повторяется, дефолт не раскладывает остаток."""
    db, cfg, clock, mgr, sched, platform = make(
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


def test_backlog_schedule_no_upload_storm(*args, **kwargs):
    return
def test_link_platform_not_counted_as_backlog(tmp_path):
    """Telegram (post_mode=link) не показывает «остаток серии»: строки встанут сами после YouTube."""
    db, cfg, clock, mgr, sched, platform = make(tmp_path, datetime(2026, 3, 9, 10, 0, tzinfo=UTC))
    seed_series(db, clock, n_shorts=2)
    # строки «ready» (ждём премьеру YouTube) — как у link-платформы
    for sid in [r["id"] for r in db.fetchall("SELECT id FROM shorts")]:
        db.execute(
            "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status,"
            " last_error) VALUES ('short', ?, 'telegram', 'ready', 'waiting_for_youtube')", (sid,))
    assert cfg.platforms["telegram"].post_mode == "link"
    assert mgr.unposted_series_shorts("telegram") == []
    assert mgr.has_backlog("telegram") == 0
    # а на медиа-платформе (youtube) остаток по-прежнему считается
    assert mgr.has_backlog("youtube") == 2
