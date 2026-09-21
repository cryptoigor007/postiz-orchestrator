"""P0.9–P0.11: раздельный state soft-end/backlog, effective-слоты backlog, диалог ask_series_end."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.backlog import BacklogManager  # noqa: E402
from orchestrator.clock import FakeClock  # noqa: E402
from orchestrator.config import load_config  # noqa: E402
from orchestrator.db import Database  # noqa: E402
from orchestrator.postiz import MockPostizClient  # noqa: E402
from orchestrator.publisher import Publisher  # noqa: E402
from orchestrator.safety import SafetyChecker  # noqa: E402
from orchestrator.scheduler import Scheduler  # noqa: E402
from orchestrator.tail import TailManager  # noqa: E402
from orchestrator.telegram_bot import TelegramNotifier  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def make(tmp_path, when=None, platform="youtube"):
    db = Database(tmp_path / "p0.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(when or datetime(2026, 9, 21, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    tail = TailManager(db, cfg, clock, tg)
    mgr = BacklogManager(db, cfg, clock, scheduler=sched)
    return {"db": db, "cfg": cfg, "clock": clock, "tail": tail, "mgr": mgr,
            "sched": sched, "tg": tg, "postiz": postiz}


# --- P0.9: soft-end и backlog — независимые состояния ---

def test_soft_end_expire_does_not_clear_backlog(tmp_path):
    e = make(tmp_path)
    db, tail, clock = e["db"], e["tail"], e["clock"]
    past = (clock.now() - timedelta(days=30)).isoformat()
    db.execute(
        "UPDATE platform_queue_state SET pending_series_end_question=1, "
        "pending_series_end_at=?, last_long_video_at=? WHERE platform='youtube'",
        (past, past))
    db.execute(
        "UPDATE platform_queue_state SET pending_backlog_question=1, pending_backlog_at=? "
        "WHERE platform='youtube'", (clock.now().isoformat(),))
    n = tail.expire_pending_questions()
    assert n == 1
    st = db.fetchone("SELECT * FROM platform_queue_state WHERE platform='youtube'")
    assert st["pending_series_end_question"] == 0        # soft-end истёк
    assert st["pending_backlog_question"] == 1           # backlog НЕ тронут
    assert e["mgr"].awaiting("youtube") is True


def test_tail_reset_does_not_clear_backlog(tmp_path):
    e = make(tmp_path)
    db, tail, clock = e["db"], e["tail"], e["clock"]
    now_iso = clock.now().isoformat()
    db.execute(
        "UPDATE platform_queue_state SET pending_series_end_question=1, pending_series_end_at=?, "
        "pending_backlog_question=1, pending_backlog_at=?, series_tail_mode=1 "
        "WHERE platform='youtube'", (now_iso, now_iso))
    tail.on_new_long_video("youtube", 7, at=now_iso)  # reset tail
    st = db.fetchone("SELECT * FROM platform_queue_state WHERE platform='youtube'")
    assert st["pending_series_end_question"] == 0        # soft-end очищен
    assert st["pending_backlog_question"] == 1           # backlog остался
    assert e["mgr"].awaiting("youtube") is True


def test_migration_v13_moves_pending_to_backlog(tmp_path):
    db = Database(tmp_path / "m.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    db.execute(
        "UPDATE platform_queue_state SET pending_series_end_question=1, "
        "pending_series_end_at='2026-01-01T00:00:00+00:00' WHERE platform='youtube'")
    db.execute("UPDATE system_state SET value='12' WHERE key='schema_version'")
    db2 = Database(tmp_path / "m.sqlite")  # повторное открытие → миграция v13
    st = db2.fetchone("SELECT * FROM platform_queue_state WHERE platform='youtube'")
    assert st["pending_backlog_question"] == 1
    assert st["pending_backlog_at"] == "2026-01-01T00:00:00+00:00"
    assert st["pending_series_end_question"] == 0
    ver = db2.fetchone("SELECT value FROM system_state WHERE key='schema_version'")["value"]
    assert ver == "13"


# --- P0.10: backlog-слоты из effective (override) ---

def test_backlog_next_slot_uses_effective_override(tmp_path):
    e = make(tmp_path)
    db, mgr, clock, cfg_timezone = e["db"], e["mgr"], e["clock"], e["cfg"].timezone
    # override: long только в воскресенье 10:00 (вместо вт/пт 16:00)
    db.execute(
        "INSERT INTO system_state (key, value, updated_at) VALUES ('schedule_settings', ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        ('{"youtube": {"long": {"days": ["sun"], "time": "10:00"}}}', clock.now().isoformat()))
    from zoneinfo import ZoneInfo

    slot = mgr.next_long_slot("youtube")
    assert slot is not None
    local = slot.astimezone(ZoneInfo(cfg_timezone))
    assert local.weekday() == 6 and (local.hour, local.minute) == (10, 0)


def test_scheduler_blocks_on_backlog_pending(tmp_path):
    e = make(tmp_path)
    db, clock, sched = e["db"], e["clock"], e["sched"]
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, vertical_path, "
        "title_text, created_at) VALUES ('videomaker','/S1','S1','/S1/w.mp4','/S1/v.mp4','S1',?)",
        (now,))
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    db.execute("UPDATE platform_queue_state SET pending_backlog_question=1, pending_backlog_at=? "
               "WHERE platform='youtube'", (now,))
    out = sched.schedule_long_videos()
    placed = [r for r in (out if isinstance(out, list) else []) if r.get("video_id") == vid]
    assert not placed  # платформа заблокирована pending backlog


# --- P0.11: ask_series_end регистрирует диалог ---

def test_ask_series_end_registers_dialog_and_reply(tmp_path):
    e = make(tmp_path)
    db, cfg, tg, clock = e["db"], e["cfg"], e["tg"], e["clock"]
    chat = (cfg.telegram.allowed_chat_ids or [1])[0]
    tg.ask_series_end("youtube")
    assert tg._pending_dialogs.get(chat, {}).get("type") == "series_end"
    db.execute("UPDATE platform_queue_state SET pending_series_end_question=1, "
               "pending_series_end_at=? WHERE platform='youtube'", (clock.now().isoformat(),))
    out = tg.handle_update(chat, "да")
    assert "ON" in out
    st = db.fetchone("SELECT * FROM platform_queue_state WHERE platform='youtube'")
    assert st["series_tail_mode"] == 1
    assert st["pending_series_end_question"] == 0  # диалог закрыл и pending
    assert tg._pending_dialogs.get(chat) is None


def test_backlog_methods_are_on_class():
    """N1 из аудита: методы backlog должны быть на классе (не внутри setup_commands)."""
    for name in ("ask_backlog", "remind_backlog", "backlog_distributed", "broadcast_markup",
                 "ask_series_end"):
        assert callable(getattr(TelegramNotifier, name, None)), f"{name} отсутствует на классе"


def test_pause_platform_upsert_without_row(tmp_path):
    """P1.4: pause/resume работают, даже если строки platform_safety_state нет."""
    e = make(tmp_path, platform="instagram")
    db, cfg, clock = e["db"], e["cfg"], e["clock"]
    db.execute("DELETE FROM platform_safety_state WHERE platform='instagram'")
    from orchestrator.safety import SafetyChecker

    safety = SafetyChecker(db, cfg, clock)
    safety.pause_platform("instagram", "manual")
    row = db.fetchone("SELECT * FROM platform_safety_state WHERE platform='instagram'")
    assert row and row["is_paused"] == 1
    assert safety.is_platform_paused("instagram") is True
    safety.resume_platform("instagram")
    assert safety.is_platform_paused("instagram") is False


def test_test_post_ttl_autocleanup(tmp_path):
    """P1.3: тест-пост старше TTL снимается; свежий и боевой — нет."""
    e = make(tmp_path)
    db, clock, postiz = e["db"], e["clock"], e["postiz"]
    cfg = e["cfg"]
    cfg.test_publish.cleanup_after_hours = 24
    from orchestrator.test_publish import cleanup_expired_test_posts

    old_post = postiz.create_post(platform="youtube", media=None,
                                  content={"description": "old"}, scheduled_for=None)
    fresh_post = postiz.create_post(platform="youtube", media=None,
                                    content={"description": "fresh"}, scheduled_for=None)
    combat = postiz.create_post(platform="youtube", media=None,
                                content={"description": "combat"}, scheduled_for=None)
    db.log("short", 1, "youtube", "test_scheduled",
           f"{old_post.id} @ 2026-01-01T00:00:00+00:00")
    db.log("short", 2, "youtube", "test_scheduled",
           f"{fresh_post.id} @ {clock.now().isoformat()}")
    db.execute("UPDATE publish_log SET created_at=? WHERE details LIKE ?",
               ((clock.now() - timedelta(hours=48)).isoformat(), f"{old_post.id}%"))
    n = cleanup_expired_test_posts(e)
    assert n == 1
    assert old_post.id not in postiz.posts        # снят
    assert fresh_post.id in postiz.posts          # свежий цел
    assert combat.id in postiz.posts              # боевой не тронут
    assert db.fetchall("SELECT 1 FROM publish_log WHERE action='test_auto_cancelled'")


def test_rate_limit_identity_stable_across_initdata(tmp_path):
    """P1.8: identity = key (или user id), а не полный initData (он меняется каждый раз)."""
    e = make(tmp_path)
    from orchestrator.webapp_api import WebAppAPI

    api = WebAppAPI(e)
    import os

    os.environ["WEBAPP_RATE_LIMIT"] = "2"
    h1 = {"X-Webapp-Key": "K1", "X-Telegram-Init-Data": "auth_date=1&hash=aaa"}
    h2 = {"X-Webapp-Key": "K1", "X-Telegram-Init-Data": "auth_date=2&hash=bbb"}
    assert api._rate_limited(h1) is False
    assert api._rate_limited(h2) is False
    assert api._rate_limited(h1) is True  # 3-й запрос того же клиента → лимит
    # другой ключ — свой bucket
    assert api._rate_limited({"X-Webapp-Key": "K2"}) is False
    os.environ.pop("WEBAPP_RATE_LIMIT", None)


def test_direct_youtube_delete_does_not_lie():
    """P1.9: delete не возвращает True при ошибке транспорта."""
    import pytest as _pytest

    from orchestrator.engines.direct_youtube import YouTubeEngine

    class BadHttp:
        def request(self, *a, **kw):
            raise RuntimeError("HTTP 403")

    eng = YouTubeEngine(token_provider=lambda: "t", http=BadHttp())
    with _pytest.raises(RuntimeError):
        eng.delete("vid123")
