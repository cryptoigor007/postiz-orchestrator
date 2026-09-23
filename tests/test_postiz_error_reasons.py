"""Причины ошибок Postiz в нашей БД: обложка — предупреждение, прочее — текст причины.

Регрессы:
  A. «Your account is not verified, we have uploaded your video but we could not set the
     thumbnail» — видео на канале, не встала только обложка: публикация состоялась
     (status=published + пометка), а не провал.
  C. В entity_platform_status.last_error должна попадать человекочитаемая причина
     (Postiz отдаёт её в /public/v1/notifications), а не безликое `postiz_error`.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.postiz import MockPostizClient
from orchestrator.postiz_errors import (
    is_thumbnail_only_error,
    parse_error_notification,
    short_reason,
)
from orchestrator.status_sync import ERROR_REASON_LIMIT, StatusSync

ROOT = Path(__file__).resolve().parents[1]

THUMB_MSG = ("Your account is not verified, we have uploaded your video but we could not "
             "set the thumbnail. Please verify your account and try again.")


def make(tmp_path, when=datetime(2026, 9, 23, 10, 0, tzinfo=UTC)):
    db = Database(tmp_path / "s.sqlite")
    db.ensure_platform_states(["youtube", "telegram"])
    cfg = load_config(ROOT / "config.yaml")
    clock = FakeClock(when)
    postiz = MockPostizClient()
    return db, cfg, clock, postiz


def seed(db, eid, platform="youtube", status="error", pid="p1",
         sched="2026-09-23T09:00:00+00:00", last_error="postiz_error"):
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_post_id, postiz_scheduled_for, last_error) VALUES ('short', ?, ?, ?, ?, ?, ?)",
        (eid, platform, status, pid, sched, last_error),
    )


def row(db, eid, platform="youtube"):
    return db.fetchone(
        "SELECT status, last_error, published_at, release_url FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=? AND platform=?", (eid, platform))


# ---------- чистые функции разбора ----------


def test_parse_error_notification_extracts_platform_and_reason():
    parsed = parse_error_notification(
        f"An error occurred while posting on youtube: {THUMB_MSG}")
    assert parsed == ("youtube", THUMB_MSG)
    assert parse_error_notification(
        "Your post has been published on Youtube at https://youtu.be/x") is None
    assert parse_error_notification("") is None


def test_is_thumbnail_only_error_matches_real_message_only():
    assert is_thumbnail_only_error(THUMB_MSG) is True
    assert is_thumbnail_only_error(THUMB_MSG.lower()) is True
    assert is_thumbnail_only_error("ETELEGRAM: 413 Request Entity Too Large") is False
    assert is_thumbnail_only_error("") is False
    # упоминание обложки в другой ошибке не делает её «ошибкой обложки»
    assert is_thumbnail_only_error("thumbnail upload rejected, video skipped") is False


def test_short_reason_is_single_line_and_capped():
    assert short_reason("a\n\nb   c") == "a b c"
    assert len(short_reason("x" * 1000, 40)) == 40


# ---------- A: ошибка обложки не помечает публикацию провалом ----------


def test_thumbnail_error_marks_published_with_warning(tmp_path):
    db, cfg, clock, postiz = make(tmp_path)
    post = postiz.create_post("youtube", None, {"title": "t"},
                              datetime(2026, 9, 23, 9, 0, tzinfo=UTC))
    postiz.set_status(post.id, "error")
    postiz.add_error_notification(
        f"An error occurred while posting on youtube: {THUMB_MSG}",
        "2026-09-23T09:00:17.744Z")
    seed(db, 399, pid=post.id)

    StatusSync(db, postiz, clock, cfg).sync()

    r = row(db, 399)
    assert r["status"] == "published"          # не провал: видео на канале
    assert r["published_at"]
    assert r["last_error"].startswith("Опубликовано без обложки")
    assert THUMB_MSG[:40] in r["last_error"]   # причина видна владельцу
    log = db.fetchall("SELECT action FROM publish_log "
                      "WHERE entity_type='short' AND entity_id=399")
    assert [x["action"] for x in log] == ["published_without_cover"]


def test_thumbnail_error_keeps_release_url(tmp_path):
    db, cfg, clock, postiz = make(tmp_path)
    post = postiz.create_post("youtube", None, {"title": "t"},
                              datetime(2026, 9, 23, 9, 0, tzinfo=UTC))
    postiz.mark_published(post.id, "https://youtu.be/abc")
    postiz.set_status(post.id, "error")       # set_status сохраняет release_url
    postiz.add_error_notification(
        f"An error occurred while posting on youtube: {THUMB_MSG}",
        "2026-09-23T09:00:20Z")
    seed(db, 400, pid=post.id)

    StatusSync(db, postiz, clock, cfg).sync()
    assert row(db, 400)["release_url"] == "https://youtu.be/abc"


def test_thumbnail_fix_is_idempotent(tmp_path):
    """Повторная синхронизация не переписывает пометку (и не дублирует лог)."""
    db, cfg, clock, postiz = make(tmp_path)
    post = postiz.create_post("youtube", None, {"title": "t"},
                              datetime(2026, 9, 23, 9, 0, tzinfo=UTC))
    postiz.set_status(post.id, "error")
    postiz.add_error_notification(
        f"An error occurred while posting on youtube: {THUMB_MSG}",
        "2026-09-23T09:00:17Z")
    seed(db, 399, pid=post.id)

    sync = StatusSync(db, postiz, clock, cfg)
    sync.sync()
    first = row(db, 399)
    clock.set(clock.now().replace(minute=30))
    sync.sync()
    second = row(db, 399)
    assert second["last_error"] == first["last_error"]
    assert second["published_at"] == first["published_at"]
    assert db.fetchone("SELECT COUNT(*) AS c FROM publish_log "
                       "WHERE action='published_without_cover'")["c"] == 1


# ---------- C: причина ошибки доходит до панели ----------


def test_other_error_stores_readable_reason(tmp_path):
    db, cfg, clock, postiz = make(tmp_path)
    post = postiz.create_post("telegram", None, {"title": "t"},
                              datetime(2026, 9, 22, 13, 0, tzinfo=UTC))
    postiz.set_status(post.id, "error")
    postiz.add_error_notification(
        "An error occurred while posting on telegram: ETELEGRAM: 413 Request Entity Too Large",
        "2026-09-22T13:00:01.397Z")
    seed(db, 270, platform="telegram", pid=post.id,
         sched="2026-09-22T13:00:00+00:00")

    StatusSync(db, postiz, clock, cfg).sync()

    r = row(db, 270, "telegram")
    assert r["status"] == "error"
    assert "413 Request Entity Too Large" in r["last_error"]
    assert r["last_error"] != "postiz_error"


def test_reason_from_post_payload_is_used(tmp_path):
    """Если Postiz отдал текст ошибки в самом посте — берём его без уведомлений."""
    db, cfg, clock, postiz = make(tmp_path)
    post = postiz.create_post("youtube", None, {"title": "t"},
                              datetime(2026, 9, 23, 9, 0, tzinfo=UTC))
    postiz.set_error(post.id, "quota exceeded for uploads")
    seed(db, 1, pid=post.id)

    StatusSync(db, postiz, clock, cfg).sync()
    assert "quota exceeded for uploads" in row(db, 1)["last_error"]


def test_reason_is_capped_for_panel(tmp_path):
    db, cfg, clock, postiz = make(tmp_path)
    post = postiz.create_post("telegram", None, {"title": "t"},
                              datetime(2026, 9, 22, 13, 0, tzinfo=UTC))
    postiz.set_status(post.id, "error")
    postiz.add_error_notification(
        "An error occurred while posting on telegram: " + "x" * 1000,
        "2026-09-22T13:00:01Z")
    seed(db, 5, platform="telegram", pid=post.id,
         sched="2026-09-22T13:00:00+00:00")

    StatusSync(db, postiz, clock, cfg).sync()
    err = row(db, 5, "telegram")["last_error"]
    assert len(err) <= ERROR_REASON_LIMIT
    assert err.endswith("…")


def test_reason_not_taken_from_other_platform(tmp_path):
    db, cfg, clock, postiz = make(tmp_path)
    post = postiz.create_post("telegram", None, {"title": "t"},
                              datetime(2026, 9, 22, 13, 0, tzinfo=UTC))
    postiz.set_status(post.id, "error")
    postiz.add_error_notification(
        f"An error occurred while posting on youtube: {THUMB_MSG}",
        "2026-09-22T13:00:01Z")
    seed(db, 6, platform="telegram", pid=post.id,
         sched="2026-09-22T13:00:00+00:00")

    StatusSync(db, postiz, clock, cfg).sync()
    r = row(db, 6, "telegram")
    assert r["status"] == "error"
    assert r["last_error"] == "postiz_error"   # чужую причину не подставляем


def test_without_notifications_keeps_old_fallback(tmp_path):
    """Нет ответа Postiz — прежнее поведение (панель показывает «ошибка на стороне Postiz»)."""
    db, cfg, clock, postiz = make(tmp_path)
    post = postiz.create_post("youtube", None, {"title": "t"},
                              datetime(2026, 9, 23, 9, 0, tzinfo=UTC))
    postiz.set_status(post.id, "error")
    seed(db, 7, pid=post.id)

    StatusSync(db, postiz, clock, cfg).sync()
    assert row(db, 7)["last_error"] == "postiz_error"


def test_two_errored_posts_get_their_own_reason(tmp_path):
    """Уведомления не переиспользуются: у каждой строки своя причина."""
    db, cfg, clock, postiz = make(tmp_path)
    first = postiz.create_post("youtube", None, {"title": "a"},
                               datetime(2026, 9, 23, 9, 0, tzinfo=UTC))
    second = postiz.create_post("youtube", None, {"title": "b"},
                                datetime(2026, 9, 23, 15, 0, tzinfo=UTC))
    postiz.set_status(first.id, "error")
    postiz.set_status(second.id, "error")
    postiz.add_error_notification("An error occurred while posting on youtube: quota A",
                                  "2026-09-23T09:00:17Z")
    postiz.add_error_notification("An error occurred while posting on youtube: quota B",
                                  "2026-09-23T15:00:48Z")
    seed(db, 399, pid=first.id, sched="2026-09-23T09:00:00+00:00")
    seed(db, 400, pid=second.id, sched="2026-09-23T15:00:00+00:00")

    StatusSync(db, postiz, clock, cfg).sync()
    assert "quota A" in row(db, 399)["last_error"]
    assert "quota B" in row(db, 400)["last_error"]


def test_existing_bare_postiz_error_gets_reason_backfilled(tmp_path):
    """Строка уже в error с безликим postiz_error — после фикса причина дописывается."""
    db, cfg, clock, postiz = make(tmp_path)
    post = postiz.create_post("youtube", None, {"title": "t"},
                              datetime(2026, 9, 23, 9, 0, tzinfo=UTC))
    postiz.set_status(post.id, "error")
    postiz.add_error_notification(
        "An error occurred while posting on youtube: upload failed: quota exceeded",
        "2026-09-23T09:00:10Z")
    seed(db, 399, status="error", pid=post.id)

    StatusSync(db, postiz, clock, cfg).sync()
    assert "quota exceeded" in row(db, 399)["last_error"]
