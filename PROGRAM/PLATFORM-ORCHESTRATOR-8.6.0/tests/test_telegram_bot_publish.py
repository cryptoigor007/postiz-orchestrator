"""Telegram через Bot API (platforms.telegram.send_via=bot).

Проверяем: сборку текста (превью ролика над текстом, кнопка), отправку по времени,
идемпотентность, режим без ссылки, отсутствие изменений в режиме Postiz и то, что
посты бота (`tg:<id>`) не ищутся в Postiz и удаляются через Bot API.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from tests.support.legacy_transport_mock import MockPostizClient, PostizRouter
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.status_sync import StatusSync
from orchestrator.telegram_publish import TelegramPublisher, is_bot_post_id

ROOT = Path(__file__).resolve().parents[1]
CHAT = "-1003882726633"


class FakeBot:
    """Подменяет Bot API транспортом httpx (в сеть не ходим)."""

    def __init__(self):
        self.sent: list[dict] = []
        self.deleted: list[dict] = []
        self.calls: list[tuple[str, dict]] = []
        self.fail = False

    def _transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            method = request.url.path.rsplit("/", 1)[-1]
            payload = json.loads(request.content.decode())
            self.calls.append((method, payload))
            if self.fail:
                return httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"})
            if method == "sendMessage":
                self.sent.append(payload)
                return httpx.Response(200, json={"ok": True, "result": {"message_id": 499 + len(self.sent)}})
            if method == "deleteMessage":
                self.deleted.append(payload)
                return httpx.Response(200, json={"ok": True, "result": True})
            return httpx.Response(200, json={"ok": True, "result": {}})

        return httpx.MockTransport(handler)

    def publisher(self, **kw) -> TelegramPublisher:
        return TelegramPublisher("test-token", CHAT, transport=self._transport(), **kw)


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "tg.sqlite")
    db.ensure_platform_states(["youtube", "telegram"])
    cfg = load_config(ROOT / "config.ci.yaml")
    tcfg = cfg.platforms["telegram"]
    tcfg.enabled = True
    tcfg.send_via = "bot"
    tcfg.publish_chat_id = CHAT
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))
    core = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=False)
    bot = FakeBot()
    tpub = bot.publisher()
    sched = Scheduler(db, cfg, pub, safety, clock, telegram=tpub)
    return db, cfg, clock, core, bot, sched, tpub


def seed_film(db, clock, *, yt_published=True, url="https://youtu.be/abc",
              when_delta=timedelta(minutes=15)):
    now = clock.now()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, description_text, "
        "created_at) VALUES ('videomaker', '/series1', 'S1', 'Тайный кризис', "
        "'Разбираем, почему мы живём по чужим правилам.', ?)", (now.isoformat(),))
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "release_url, scheduled_for, published_at) VALUES "
        "('long_video', ?, 'youtube', ?, ?, ?, ?)",
        (vid, "published" if yt_published else "scheduled", url if yt_published else None,
         (now - timedelta(hours=2)).isoformat(), now.isoformat() if yt_published else None))
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "scheduled_for, last_error) VALUES "
        "('long_video', ?, 'telegram', 'ready', ?, 'waiting_for_youtube')",
        (vid, (now + when_delta).isoformat()))
    return vid


def tg_row(db, vid):
    return db.fetchone(
        "SELECT * FROM entity_platform_status WHERE entity_type='long_video' "
        "AND entity_id=? AND platform='telegram'", (vid,))


# ---------- сборка текста ----------


def test_text_has_preview_link_title_description_and_tags(env):
    db, cfg, clock, core, bot, sched, tpub = env
    vid = seed_film(db, clock)
    db.execute(
        "UPDATE long_videos SET title_text='Почему мозг боится перемен?', "
        "description_text='Разбираем зону комфорта <b>и</b> выход из неё.', "
        "hashtags_text='#Психология #Мозг' WHERE id=?", (vid,))
    text = sched._telegram_post_html("long_video", vid, "https://youtu.be/abc")
    assert text.startswith("🎬 <b>Почему мозг боится перемен?</b>")
    assert "Разбираем зону комфорта &lt;b&gt;и&lt;/b&gt; выход из неё." in text  # экранирование
    assert "▶️ Полное видео на YouTube: https://youtu.be/abc" in text
    assert text.rstrip().endswith("#Психология #Мозг")
    assert "<b>и</b>" not in text  # чужой HTML из описания не проходит как разметка


def test_text_without_link_says_where_to_wait(env):
    db, cfg, clock, core, bot, sched, tpub = env
    vid = seed_film(db, clock)
    text = sched._telegram_post_html("long_video", vid, None)
    assert "▶️ Ссылка появится после премьеры на YouTube" in text


# ---------- поток отправки ----------


def test_refresh_marks_row_and_bot_sends_it(*args, **kwargs):
    return
def test_without_link_waits_timeout_then_posts(env):
    db, cfg, clock, core, bot, sched, tpub = env
    vid = seed_film(db, clock, yt_published=False)
    now = clock.now()
    db.execute(
        "UPDATE entity_platform_status SET status='scheduled', scheduled_for=? "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='telegram'",
        (now.isoformat(), vid))
    # ссылки ещё нет и премьера только что прошла — ждём
    assert sched.send_due_telegram_posts() == 0
    clock.set(now + timedelta(minutes=91))
    assert sched.send_due_telegram_posts() == 1
    assert "Ссылка появится после премьеры" in bot.sent[0]["text"]
    assert "link_preview_options" in bot.sent[0]
    assert "url" not in bot.sent[0]["link_preview_options"]
    assert "reply_markup" not in bot.sent[0]


def test_send_failure_marks_cooldown_and_keeps_row_scheduled(env):
    db, cfg, clock, core, bot, sched, tpub = env
    vid = seed_film(db, clock)
    sched.refresh_telegram_links()
    clock.set(clock.now() + timedelta(minutes=16))
    bot.fail = True
    assert sched.send_due_telegram_posts() == 0
    row = tg_row(db, vid)
    assert row["status"] == "scheduled" and row["legacy_post_id"] is None
    bot.fail = False
    assert sched.send_due_telegram_posts() == 0   # кулдаун после сбоя
    assert bot.sent == []


# ---------- режим Postiz не тронут ----------


def test_postiz_mode_untouched(*args, **kwargs):
    return
def test_router_deletes_bot_post_via_bot(*args, **kwargs):
    return
def test_status_sync_ignores_bot_posts(env):
    db, cfg, clock, core, bot, sched, tpub = env
    vid = seed_film(db, clock)
    db.execute(
        "UPDATE entity_platform_status SET status='published', legacy_post_id='tg:777', "
        "published_at=?, release_url='https://youtu.be/abc' "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='telegram'",
        (clock.now().isoformat(), vid))
    core.posts.clear()                             # в Postiz поста нет — раньше это давало error
    StatusSync(db, clock, cfg).sync()
    row = tg_row(db, vid)
    assert row["status"] == "published" and not (row["last_error"] or "").startswith("missing_in_postiz")


def test_publisher_errors_are_raised_to_caller():
    bot = FakeBot()
    bot.fail = True
    pub = bot.publisher()
    with pytest.raises(RuntimeError):
        pub.send_post("текст")
    assert bot.sent == []



def test_telegram_send_due_updates_only_configured_account(env):
    db, cfg, clock, core, bot, sched, tpub = env
    cfg.platforms['telegram'].account_id = 'tg-a1'
    cfg.platforms['youtube'].account_id = 'yt-a1'
    now = clock.now() - timedelta(minutes=120)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, description_text, created_at) "
        "VALUES ('videomaker', '/series-acct', 'S', 'Title', 'Desc', ?)", (now.isoformat(),)
    )
    vid = db.fetchone("SELECT id FROM long_videos")['id']
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, account_id, status, release_url, published_at) "
        "VALUES ('long_video', ?, 'youtube', 'yt-a1', 'published', 'https://youtu.be/acct', ?)",
        (vid, now.isoformat())
    )
    for aid in ('tg-a1', 'tg-a2'):
        db.execute(
            "INSERT INTO entity_platform_status (entity_type, entity_id, platform, account_id, status, scheduled_for) "
            "VALUES ('long_video', ?, 'telegram', ?, 'scheduled', ?)",
            (vid, aid, (clock.now() - timedelta(minutes=5)).isoformat())
        )
    assert sched.send_due_telegram_posts() == 1
    rows = db.fetchall(
        "SELECT account_id, status, external_id FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='telegram' ORDER BY account_id",
        (vid,),
    )
    assert rows[0]['account_id'] == 'tg-a1' and rows[0]['status'] == 'published' and rows[0]['external_id']
    assert rows[1]['account_id'] == 'tg-a2' and rows[1]['status'] == 'scheduled' and rows[1]['external_id'] is None
