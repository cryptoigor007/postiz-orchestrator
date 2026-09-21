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


def test_rate_limit_bucket_uses_validated_uid(tmp_path, monkeypatch):
    """R2/R5: bucket по uid из HMAC-валидированного initData (разные подписи = один bucket)."""
    import hashlib
    import hmac
    import json
    import time
    from urllib.parse import urlencode

    from orchestrator.webapp_api import WebAppAPI

    e = make(tmp_path)
    api = WebAppAPI(e)
    token = "123:TEST"
    api.token = token
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    monkeypatch.setenv("WEBAPP_RATE_LIMIT", "2")
    monkeypatch.delenv("WEBAPP_ACCESS_KEY", raising=False)
    uid = (e["cfg"].telegram.allowed_chat_ids or [42])[0]

    def signed(ts: int) -> str:
        user = json.dumps({"id": uid, "first_name": "U"}, separators=(",", ":"))
        fields = {"auth_date": str(ts), "user": user}
        check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        return urlencode(fields)

    now = int(time.time())
    h1, h2 = signed(now), signed(now - 5)
    assert api._auth({"X-Telegram-Init-Data": h1}) is not None
    assert api._rate_limited({}, api._auth({"X-Telegram-Init-Data": h1})) is False
    assert api._rate_limited({}, api._auth({"X-Telegram-Init-Data": h2})) is False  # тот же uid
    assert api._rate_limited({}, api._auth({"X-Telegram-Init-Data": h1})) is True   # лимит 2/мин
    # невалидный init → uid нет → отдельный anon-bucket
    assert api._rate_limited({}, api._auth({"X-Telegram-Init-Data": "bogus=1"})) is False


# --- 8.2.2+ CSP nonce ---

def _api_env(tmp_path):
    import os

    os.environ["WEBAPP_DEV"] = "1"
    e = make(tmp_path)

    from orchestrator.link_updater import LinkUpdater
    from orchestrator.webapp_api import WebAppAPI

    e["link_upd"] = LinkUpdater(e["db"], e["cfg"], e["postiz"], e["clock"], e["tg"])
    return WebAppAPI(e)


def test_csp_nonce_in_composed_page(tmp_path):
    import re

    from orchestrator.webapp_api import WEBAPP_BUILD

    api = _api_env(tmp_path)
    code, body, ctype = api.handle("GET", f"/webapp/b/{WEBAPP_BUILD}/", {}, b"")
    assert code == 200
    html = body.decode() if isinstance(body, bytes) else str(body)
    nonces = set(re.findall(r'nonce="([^"]+)"', html))
    assert len(nonces) == 1, "стиль и оба скрипта должны иметь один nonce"
    n = nonces.pop()
    assert html.count(f'<script nonce="{n}">') == 2
    assert html.count(f'<style nonce="{n}">') == 1
    assert "telegram-web-app.js" in html


def test_csp_header_has_nonce_without_script_unsafe_inline(tmp_path):
    import socket
    import urllib.request

    from orchestrator.http_server import start_http_server
    from orchestrator.webapp_api import WEBAPP_BUILD

    api = _api_env(tmp_path)
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = start_http_server(port, lambda: {"ok": True}, api.handle)
    assert srv is not None
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/webapp/b/{WEBAPP_BUILD}/", timeout=5
            ) as r:
            csp = r.headers.get("Content-Security-Policy") or ""
            html = r.read().decode()
        assert "script-src 'self' https://telegram.org 'nonce-" in csp
        assert "'unsafe-inline'" not in csp.split("style-src")[0], "script-src не должен иметь unsafe-inline"
        assert "style-src 'self' 'unsafe-inline'" in csp  # осознанно (style-атрибуты UI)
        n = csp.split("'nonce-")[1].split("'")[0]
        assert f'nonce="{n}"' in html, "nonce из заголовка должен совпадать с телом"
    finally:
        srv.shutdown()


def test_transport_send_message_429_backoff(monkeypatch):
    """P1.10: 429 от Bot API → пауза Retry-After и один повтор; не-ok логируется."""
    import httpx

    from orchestrator.telegram_transport import TelegramTransport

    calls = {"post": 0, "sleep": []}

    class Resp:
        def __init__(self, code, ok, retry_after=None):
            self.status_code = code
            self._ok = ok
            self.text = "{}"
            self._ra = retry_after

        def json(self):
            d = {"ok": self._ok}
            if self._ra is not None:
                d["parameters"] = {"retry_after": self._ra}
            return d

    def fake_post(url, **kw):
        calls["post"] += 1
        if calls["post"] == 1:
            return Resp(429, False, retry_after=2)
        return Resp(200, True)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr("time.sleep", lambda s: calls["sleep"].append(s))
    t = TelegramTransport(token="123:TEST")
    t.send_message(1, "hello")
    assert calls["post"] == 2
    assert calls["sleep"] == [2.0]


def test_auto_cancelled_excluded_from_cleanup_active(tmp_path):
    """Живая находка: после test_auto_cancelled повторные DELETE не выполняются."""
    e = make(tmp_path)
    db, clock, postiz = e["db"], e["clock"], e["postiz"]
    e["cfg"].test_publish.cleanup_after_hours = 24
    from orchestrator.test_publish import cleanup_expired_test_posts

    post = postiz.create_post(platform="youtube", media=None,
                              content={"description": "aged"}, scheduled_for=None)
    db.execute("INSERT INTO publish_log (entity_type, entity_id, platform, action, details, created_at) "
               "VALUES ('short', 1, 'youtube', 'test_scheduled', ?, ?)",
               (f"{post.id} @ 2026-01-01T00:00:00+00:00",
                (clock.now() - timedelta(hours=48)).isoformat()))
    assert cleanup_expired_test_posts(e) == 1
    # повторный прогон: авто-снятый уже не в active → 0 и никаких DELETE
    calls = {"n": 0}
    real_delete = postiz.delete_post

    def counting_delete(pid):
        calls["n"] += 1
        return real_delete(pid)

    postiz.delete_post = counting_delete
    assert cleanup_expired_test_posts(e) == 0
    assert calls["n"] == 0


def test_httpx_logger_quiet_after_main_setup():
    """SEC: httpx/httpcore не логируют URL с токеном (уровень >= WARNING)."""
    import logging as _lg

    import orchestrator.main  # noqa: F401  (модуль настраивает логгеры при импорте)

    assert _lg.getLogger("httpx").level >= _lg.WARNING
    assert _lg.getLogger("httpcore").level >= _lg.WARNING
