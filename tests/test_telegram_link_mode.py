"""Telegram в режиме `post_mode: link`: канал получает ССЫЛКУ, а не файл.

Регрессы:
  B. «Остаток серии» раскладывался через schedule_backlog() без оглядки на post_mode,
     поэтому в Telegram уходил файл шортса (138 МБ) — Bot API отвечал 413, а у нас
     фиксировалась ошибка «файл больше лимита». В link-режиме файл не должен даже
     загружаться: пост-ссылку отправляет Bot API (TelegramPublisher.send_post).
  B'. То же — на уровне Publisher: любой путь с медиа для link-платформы теряет файл.
  A'. Если YouTube-ссылки так и не появилось (видео вышло, но Postiz не отдал URL),
     строка «ждёт выхода на YouTube» не должна висеть вечно — уходит пост с плейсхолдером.
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
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.status_sync import StatusSync
from orchestrator.telegram_publish import TelegramPublisher

ROOT = Path(__file__).resolve().parents[1]
CHAT = "-1003882726633"
MONDAY = datetime(2026, 3, 9, 10, 0, tzinfo=UTC)   # 13:00 MSK


class FakeBot:
    """Подменяет Bot API транспортом httpx (в сеть не ходим)."""

    def __init__(self):
        self.sent: list[dict] = []

    def _transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            method = request.url.path.rsplit("/", 1)[-1]
            payload = json.loads(request.content.decode())
            if method == "sendMessage":
                self.sent.append(payload)
                return httpx.Response(200, json={"ok": True,
                                                 "result": {"message_id": 700 + len(self.sent)}})
            return httpx.Response(200, json={"ok": True, "result": True})

        return httpx.MockTransport(handler)

    def publisher(self, **kw) -> TelegramPublisher:
        return TelegramPublisher("test-token", CHAT, transport=self._transport(), **kw)


def big_file(tmp_path, mb: int = 60) -> str:
    """Разреженный файл: размер есть, диск не занимаем."""
    p = tmp_path / f"short_{mb}mb.mp4"
    with p.open("wb") as f:
        f.truncate(mb * 1024 * 1024)
    return str(p)


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "tg.sqlite")
    db.ensure_platform_states(["youtube", "telegram"])
    cfg = load_config(ROOT / "config.yaml")
    tcfg = cfg.platforms["telegram"]
    tcfg.enabled = True
    tcfg.post_mode = "link"
    tcfg.send_via = "bot"
    tcfg.publish_chat_id = CHAT
    clock = FakeClock(MONDAY)
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    bot = FakeBot()
    sched = Scheduler(db, cfg, pub, safety, clock, telegram=bot.publisher())
    # канонические слоты Telegram, чтобы раскладка остатка вообще могла что-то поставить
    db.set_setting("schedule_settings", json.dumps({
        "telegram": {"long": {"days": ["mon"], "time": "18:00"},
                     "standalone": {"days": ["mon"], "times": ["19:00"]},
                     "thematic": {"time": "20:30"}},
    }))
    return db, cfg, clock, postiz, sched, bot


def seed_series(db, clock, media: str, *, yt_url="https://youtu.be/abc"):
    now = clock.now()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, created_at) "
        "VALUES ('videomaker', '/S1', 'S1', 'Серия 1', ?)", (now.isoformat(),))
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    db.execute(
        "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, video_path, "
        "title_text, description_text, created_at) VALUES "
        "('videomaker', ?, '/S1/shorts/s1', 0, ?, 'Шортс 1', 'Описание', ?)",
        (vid, media, now.isoformat()))
    sid = db.fetchone("SELECT id FROM shorts")["id"]
    # у шортса своя строка YouTube (как в бою), у Telegram — «ждёт выхода на YouTube»
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "release_url, published_at) VALUES ('short', ?, 'youtube', 'published', ?, ?)",
        (sid, yt_url, now.isoformat()))
    # серия тоже уже вышла (нужно тематическим шортсам, чтобы построить слоты)
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "release_url, published_at, postiz_scheduled_for) VALUES "
        "('long_video', ?, 'telegram', 'published', ?, ?, ?)",
        (vid, yt_url or "https://youtu.be/abc", now.isoformat(), now.isoformat()))
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for, last_error) VALUES "
        "('short', ?, 'telegram', 'ready', ?, 'waiting_for_youtube')",
        (sid, (now + timedelta(minutes=15)).isoformat()))
    return vid, sid


def tg_row(db, sid):
    return db.fetchone(
        "SELECT * FROM entity_platform_status WHERE entity_type='short' AND entity_id=? "
        "AND platform='telegram'", (sid,))


# ---------- B: ссылка, а не файл ----------


def test_backlog_does_not_send_file_to_link_platform(env, tmp_path):
    """Остаток серии для link-платформы не уходит файлом в Postiz."""
    db, cfg, clock, postiz, sched, bot = env
    _, sid = seed_series(db, clock, big_file(tmp_path, 138))

    assert sched.schedule_backlog("telegram") == 0
    assert postiz.media == {}, "файл не должен загружаться в Postiz"
    assert postiz.posts == {}, "пост в Postiz создавать нечего: Telegram — ссылка"
    assert tg_row(db, sid)["status"] == "ready"   # всё ещё ждём YouTube-ссылку


def test_big_file_goes_as_link_to_channel(env, tmp_path):
    """Файл больше порога Bot API: канал получает ссылку, файл в Postiz не уходит."""
    db, cfg, clock, postiz, sched, bot = env
    _, sid = seed_series(db, clock, big_file(tmp_path, 138))

    assert sched.refresh_telegram_links() == 1
    assert tg_row(db, sid)["status"] == "scheduled"
    clock.set(clock.now() + timedelta(minutes=16))
    assert sched.send_due_telegram_posts() == 1

    assert len(bot.sent) == 1
    payload = bot.sent[0]
    assert payload["link_preview_options"]["url"] == "https://youtu.be/abc"
    assert "youtu.be/abc" in payload["text"]
    assert postiz.media == {}, "медиа в Postiz не загружалось"
    assert postiz.posts == {}
    assert tg_row(db, sid)["status"] == "published"


def test_thematic_shorts_not_sent_as_file_to_link_platform(env, tmp_path):
    db, cfg, clock, postiz, sched, bot = env
    vid, _ = seed_series(db, clock, big_file(tmp_path, 138))

    assert sched.schedule_thematic_shorts(vid, "telegram") == 0
    assert postiz.media == {} and postiz.posts == {}


def test_publisher_drops_media_for_link_platform(env, tmp_path):
    """Страховка на уровне Publisher: любой путь с медиа для link-платформы теряет файл."""
    db, cfg, clock, postiz, sched, _bot = env
    media = big_file(tmp_path, 138)
    when = clock.now() + timedelta(minutes=10)

    post = sched.publisher.publish(
        "long_video", 1, "telegram", media,
        {"title": "t", "description": "▶ Смотреть на YouTube: https://youtu.be/abc",
         "priority": "link"}, when)

    assert post is not None
    assert postiz.media == {}, "файл не должен загружаться"
    actions = [r["action"] for r in db.fetchall(
        "SELECT action FROM publish_log WHERE platform='telegram'")]
    assert "link_mode_media_skipped" in actions


def test_media_mode_still_sends_file(tmp_path):
    """Обратная проверка: в режиме media файл по-прежнему уходит (фикс не сломал боевой путь)."""
    db = Database(tmp_path / "m.sqlite")
    db.ensure_platform_states(["telegram"])
    cfg = load_config(ROOT / "config.yaml")
    tcfg = cfg.platforms["telegram"]
    tcfg.post_mode = "media"
    tcfg.send_via = "postiz"
    clock = FakeClock(MONDAY)
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    media = big_file(tmp_path, 10)

    post = pub.publish("long_video", 1, "telegram", media,
                       {"title": "t", "description": "d"}, clock.now() + timedelta(minutes=10))

    assert post is not None
    assert len(postiz.media) == 1, "в режиме media медиа загружается как раньше"


# ---------- A': видео вышло, а ссылки нет (обложка не встала) ----------


def test_waiting_row_promoted_when_video_published_without_url(env, tmp_path):
    db, cfg, clock, postiz, sched, bot = env
    vid, sid = seed_series(db, clock, big_file(tmp_path, 10), yt_url=None)
    old = (clock.now() - timedelta(minutes=100)).isoformat()
    db.execute(
        "UPDATE entity_platform_status SET postiz_scheduled_for=? "
        "WHERE entity_type='short' AND entity_id=? AND platform='telegram'", (old, sid))

    assert sched.refresh_telegram_links() == 1
    row = tg_row(db, sid)
    assert row["status"] == "scheduled" and row["last_error"] is None

    assert sched.send_due_telegram_posts() == 1
    assert "Ссылка появится после премьеры" in bot.sent[0]["text"]
    assert postiz.media == {} and postiz.posts == {}


def test_waiting_row_not_promoted_before_timeout(env, tmp_path):
    db, cfg, clock, postiz, sched, bot = env
    vid, sid = seed_series(db, clock, big_file(tmp_path, 10), yt_url=None)
    fresh = (clock.now() - timedelta(minutes=10)).isoformat()
    db.execute(
        "UPDATE entity_platform_status SET postiz_scheduled_for=? "
        "WHERE entity_type='short' AND entity_id=? AND platform='telegram'", (fresh, sid))

    assert sched.refresh_telegram_links() == 0
    assert tg_row(db, sid)["status"] == "ready"   # ещё ждём ссылку


def test_thumbnail_error_unblocks_telegram_post_with_real_link(env, tmp_path):
    """Боевой сценарий 399/400: видео вышло, обложка не встала → telegram всё равно уходит.

    Ошибка обложки не должна превращаться в провал: синхронизация обязана забрать ссылку
    из Postiz, а телеграм-пост — перестать висеть в «ждёт выхода на YouTube».
    """
    db, cfg, clock, postiz, sched, bot = env
    _, sid = seed_series(db, clock, big_file(tmp_path, 10), yt_url=None)
    post = postiz.create_post("youtube", None, {"title": "t"}, MONDAY)
    postiz.mark_published(post.id, "https://youtu.be/real")
    postiz.set_status(post.id, "error")            # Postiz пометил пост ошибкой обложки
    postiz.add_error_notification(
        "An error occurred while posting on youtube: Your account is not verified, we have "
        "uploaded your video but we could not set the thumbnail. Please verify your account "
        "and try again.", "2026-03-09T10:00:05Z")
    db.execute(
        "UPDATE entity_platform_status SET postiz_post_id=?, postiz_scheduled_for=? "
        "WHERE entity_type='short' AND entity_id=? AND platform='youtube'",
        (post.id, MONDAY.isoformat(), sid))
    db.execute(
        "UPDATE entity_platform_status SET postiz_scheduled_for=? "
        "WHERE entity_type='short' AND entity_id=? AND platform='telegram'",
        ((clock.now() - timedelta(minutes=20)).isoformat(), sid))

    StatusSync(db, postiz, clock, cfg).sync()
    yt = db.fetchone("SELECT status, release_url, last_error FROM entity_platform_status "
                     "WHERE entity_type='short' AND entity_id=? AND platform='youtube'", (sid,))
    assert yt["status"] == "published"
    assert yt["release_url"] == "https://youtu.be/real"       # ссылка подтянута из Postiz
    assert yt["last_error"].startswith("Опубликовано без обложки")

    assert sched.refresh_telegram_links() == 1
    assert tg_row(db, sid)["status"] == "scheduled"

    clock.set(clock.now() + timedelta(minutes=20))
    assert sched.send_due_telegram_posts() == 1
    assert bot.sent[0]["link_preview_options"]["url"] == "https://youtu.be/real"
    assert "https://youtu.be/real" in bot.sent[0]["text"]
    assert postiz.media == {}, "дубль файла в Postiz не создаём и не загружаем"
