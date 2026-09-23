"""Разовая починка строк после инцидента с обложкой (tools/fix_error_rows.py).

Проверяем, что скрипт:
  * пишет точную ссылку YouTube в youtube-строку и переводит её в published,
    сохраняя пометку «Опубликовано без обложки»;
  * возвращает Telegram-пост в очередь (status='ready' + 'waiting_for_youtube'),
    убирая старую попытку отправить файл;
  * в dry-run работает на копии БД и не меняет исходную базу.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.db import Database  # noqa: E402
from orchestrator.postiz import MockPostizClient  # noqa: E402

_spec = importlib.util.spec_from_file_location("fix_error_rows", ROOT / "tools/fix_error_rows.py")
assert _spec and _spec.loader
fix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fix)


def make_db(tmp_path) -> Database:
    db = Database(tmp_path / "d.sqlite")
    db.ensure_platform_states(["youtube", "telegram"])
    db.execute(
        "INSERT INTO shorts (id, source, parent_video_id, folder_path, order_index, video_path, "
        "title_text, description_text, created_at) VALUES (399, 'videomaker', NULL, '/S/s399', 0, "
        "'/x.mp4', 'В чём истинная причина зависти?', 'Описание', '2026-09-21T10:00:00+00:00')")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_post_id, postiz_scheduled_for, last_error) VALUES ('short', 399, 'youtube', "
        "'error', 'cmuder3mo', '2026-09-23T09:00:00+00:00', 'postiz_error')")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for, last_error) VALUES ('short', 399, 'telegram', 'ready', "
        "'2026-09-23T09:15:00+00:00', 'waiting_for_youtube')")
    return db


def yt(db):
    return db.fetchone("SELECT * FROM entity_platform_status WHERE entity_type='short' "
                       "AND entity_id=399 AND platform='youtube'")


def tg(db):
    return db.fetchone("SELECT * FROM entity_platform_status WHERE entity_type='short' "
                       "AND entity_id=399 AND platform='telegram'")


def test_apply_links_publishes_with_cover_note(tmp_path):
    db = make_db(tmp_path)
    fix.apply_links(db, {399: "https://youtu.be/7xbAkPUZ1Cc"}, commit=True)

    row = yt(db)
    assert row["status"] == "published"
    assert row["release_url"] == "https://youtu.be/7xbAkPUZ1Cc"
    assert row["last_error"].startswith("Опубликовано без обложки")
    assert row["published_at"]
    assert [r["action"] for r in db.fetchall(
        "SELECT action FROM publish_log WHERE entity_id=399")] == ["release_url_restored"]


def test_apply_links_keeps_existing_cover_reason(tmp_path):
    db = make_db(tmp_path)
    db.execute("UPDATE entity_platform_status SET last_error=? WHERE entity_id=399 "
               "AND platform='youtube'", ("Опубликовано без обложки: обложку не поставили",))
    fix.apply_links(db, {399: "https://youtu.be/7xbAkPUZ1Cc"}, commit=True)
    assert yt(db)["last_error"] == "Опубликовано без обложки: обложку не поставили"


def test_apply_links_is_idempotent(tmp_path):
    db = make_db(tmp_path)
    fix.apply_links(db, {399: "https://youtu.be/7xbAkPUZ1Cc"}, commit=True)
    before = dict(yt(db))
    fix.apply_links(db, {399: "https://youtu.be/7xbAkPUZ1Cc"}, commit=True)
    assert dict(yt(db)) == before
    assert db.fetchone("SELECT COUNT(*) AS c FROM publish_log "
                       "WHERE action='release_url_restored'")["c"] == 1


def test_dry_run_does_not_write(tmp_path):
    db = make_db(tmp_path)
    fix.apply_links(db, {399: "https://youtu.be/7xbAkPUZ1Cc"}, commit=False)
    assert yt(db)["status"] == "error"
    assert yt(db)["release_url"] is None

    postiz = MockPostizClient()
    fix.requeue_telegram(db, postiz, 399, commit=False)
    assert tg(db)["status"] == "ready"


def test_requeue_telegram_returns_post_to_queue(tmp_path):
    db = make_db(tmp_path)
    db.execute("UPDATE entity_platform_status SET status='error', last_error="
               "'telegram: файл 138 МБ > лимита Bot API 50 МБ' WHERE entity_id=399 "
               "AND platform='telegram'")
    fix.requeue_telegram(db, MockPostizClient(), 399, commit=True)
    row = tg(db)
    assert row["status"] == "ready"
    assert row["last_error"] == "waiting_for_youtube"
    assert row["link_updated_at"] is None      # цикл снова возьмёт строку


def test_requeue_deletes_old_postiz_post_when_committing(tmp_path):
    """Файловый пост в Postiz больше не нужен: иначе он блокирует отправку."""
    db = make_db(tmp_path)
    postiz = MockPostizClient()
    post = postiz.create_post("telegram", None, {"description": "файл"}, None)
    db.execute("UPDATE entity_platform_status SET status='error', postiz_post_id=? "
               "WHERE entity_id=399 AND platform='telegram'", (post.id,))

    fix.requeue_telegram(db, postiz, 399, commit=True)
    assert post.id not in postiz.posts
    assert tg(db)["postiz_post_id"] is None


def test_requeue_keeps_published_bot_post(tmp_path):
    db = make_db(tmp_path)
    db.execute("UPDATE entity_platform_status SET status='published', postiz_post_id='tg:777' "
               "WHERE entity_id=399 AND platform='telegram'")
    fix.requeue_telegram(db, MockPostizClient(), 399, commit=True)
    assert tg(db)["postiz_post_id"] == "tg:777"   # уже вышел — не трогаем


def test_copy_db_leaves_source_untouched(tmp_path):
    db = make_db(tmp_path)
    src = str(tmp_path / "d.sqlite")
    copy_path = fix._copy_db(src)
    assert copy_path != src
    copy = Database(copy_path)
    fix.apply_links(copy, {399: "https://youtu.be/7xbAkPUZ1Cc"}, commit=True)
    assert yt(copy)["status"] == "published"
    assert yt(db)["status"] == "error"     # исходная база не изменилась
