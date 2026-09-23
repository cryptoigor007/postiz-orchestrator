#!/usr/bin/env python3
"""Разовая починка строк, вставших из-за ошибки обложки и файла в link-режиме.

Инцидент 2026-09-23 (см. docs/SESSION_LOG.md): у двух YouTube-постов видео
загрузилось, но не встала обложка — они были помечены провалом, и телеграм-посты
навсегда остались «ждёт выхода на YouTube». Плюс телеграм-пост, который пытались
отправить файлом 138 МБ в link-режиме.

Скрипт делает только то, что умеет код оркестратора (ручных SQL-правок нет):

  1. Прогоняет `StatusSync` — он забирает причину из Postiz и, если это ошибка
     обложки, переводит пост в `published` с пометкой «Опубликовано без обложки»
     (ссылку из Postiz сохраняет в `release_url`, если Postiz её отдал).
  2. Возвращает в очередь указанные Telegram-посты: `status='ready'`,
     `last_error='waiting_for_youtube'`. Дальше их подхватит рабочий цикл
     (`refresh_telegram_links` → `send_due_telegram_posts`) и отправит ссылку.

По умолчанию — dry-run: всё считается на КОПИИ БД (включая правки StatusSync),
боевая база не меняется. Запись только с `--commit`.

Примеры:
  ./venv/bin/python tools/fix_error_rows.py                 # посмотреть
  ./venv/bin/python tools/fix_error_rows.py --commit        # починить
  ./venv/bin/python tools/fix_error_rows.py --youtube 399,400 --telegram 270 --commit
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import SystemClock  # noqa: E402
from orchestrator.config import load_config  # noqa: E402
from orchestrator.db import Database  # noqa: E402
from orchestrator.postiz_errors import short_reason  # noqa: E402
from orchestrator.postiz_http import HttpPostizClient  # noqa: E402
from orchestrator.status_sync import StatusSync  # noqa: E402
from orchestrator.telegram_publish import is_bot_post_id  # noqa: E402

WARN_PREFIX = "Опубликовано без обложки"


def _ids(raw: str) -> list[int]:
    out: list[int] = []
    for part in str(raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part:
            out.append(int(part))
    return out


def _snapshot(db: Database, ids: list[int] | None) -> dict[tuple, dict]:
    sql = ("SELECT entity_type, entity_id, platform, status, release_url, last_error, "
           "postiz_post_id, postiz_scheduled_for, link_updated_at "
           "FROM entity_platform_status WHERE platform IN ('youtube','telegram')")
    params: tuple = ()
    if ids:
        sql += " AND entity_type='short' AND entity_id IN (%s)" % ",".join("?" * len(ids))
        params = tuple(ids)
    return {(r["entity_type"], r["entity_id"], r["platform"]): dict(r)
            for r in db.fetchall(sql, params)}


def _show_diff(before: dict, after: dict) -> int:
    changed = 0
    for key in sorted(after, key=lambda k: (k[1], k[2])):
        old, new = before.get(key, {}), after[key]
        diffs = [(f, old.get(f), new.get(f)) for f in
                 ("status", "release_url", "last_error", "postiz_post_id")
                 if old.get(f) != new.get(f)]
        if not diffs:
            continue
        if old:
            changed += 1
        print(f"  {key[0]} {key[1]} [{key[2]}]")
        for field, o, n in diffs:
            print(f"      {field}: {o!r} → {n!r}")
    return changed


def apply_links(db: Database, links: dict[int, str], commit: bool) -> None:
    """Записать в YouTube-строки шортсов точные ссылки (когда Postiz их не отдал).

    Ссылки берутся из YouTube API владельцем (при ошибке обложки Postiz оставляет
    releaseURL и releaseId пустыми — восстановить из его API нечего).
    """
    for sid, url in sorted(links.items()):
        row = db.fetchone(
            "SELECT status, release_url, last_error FROM entity_platform_status "
            "WHERE entity_type='short' AND entity_id=? AND platform='youtube'", (sid,))
        if row is None:
            print(f"  short {sid} [youtube]: строки нет — ссылку записать некуда")
            continue
        if row["status"] == "published" and row["release_url"] == url:
            print(f"  short {sid} [youtube]: уже published, ссылка на месте — ок")
            continue
        note = str(row["last_error"] or "")
        if not note.startswith(WARN_PREFIX):
            note = (f"{WARN_PREFIX}: видео на канале, обложку поставить не удалось "
                    f"(канал YouTube не подтверждён), ссылка восстановлена вручную")
        print(f"  short {sid} [youtube]: {row['status']!r} → 'published', "
              f"release_url={url!r}")
        if not commit:
            continue
        db.execute(
            "UPDATE entity_platform_status SET status='published', release_url=?, "
            "last_error=?, published_at=COALESCE(published_at, ?) "
            "WHERE entity_type='short' AND entity_id=? AND platform='youtube'",
            (url, short_reason(note, 300), datetime.now(UTC).isoformat(), sid))
        db.log("short", sid, "youtube", "release_url_restored", url)


def requeue_telegram(db: Database, postiz: HttpPostizClient, sid: int, commit: bool) -> None:
    """Вернуть Telegram-пост шортса в очередь (link-режим: уйдёт ссылка, не файл)."""
    row = db.fetchone(
        "SELECT * FROM entity_platform_status WHERE entity_type='short' AND entity_id=? "
        "AND platform='telegram'", (sid,))
    if row is None:
        print(f"  short {sid} [telegram]: строки нет — нечего возвращать "
              f"(появится сама через schedule_telegram_links)")
        return
    yt = db.fetchone(
        "SELECT status, release_url FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=? AND platform='youtube'", (sid,))
    if row["status"] == "published" and row["postiz_post_id"]:
        print(f"  short {sid} [telegram]: уже опубликован ({row['postiz_post_id']}) — не трогаем")
        return
    yt_state = "нет строки"
    if yt:
        yt_state = f"{yt['status']}" + (f", ссылка {yt['release_url']}" if yt["release_url"]
                                        else ", ссылки нет")
    print(f"  short {sid} [telegram]: {row['status']!r} → 'ready' "
          f"(last_error='waiting_for_youtube'); youtube: {yt_state}")
    old_id = row["postiz_post_id"]
    if old_id and not is_bot_post_id(old_id):
        # старый файловый пост в Postiz больше не нужен — иначе он помешает отправке
        if not commit:
            print(f"      (dry-run: при --commit удалим старый пост Postiz {old_id})")
        else:
            try:
                postiz.delete_post(str(old_id))
                print(f"      удалён старый пост Postiz {old_id}")
            except Exception as e:  # noqa: BLE001 — сообщаем, но починку не отменяем
                print(f"      не удалось удалить пост Postiz {old_id}: {e}")
    db.execute(
        "UPDATE entity_platform_status SET status='ready', last_error='waiting_for_youtube', "
        "postiz_post_id=NULL, link_updated_at=NULL, published_at=NULL "
        "WHERE entity_type='short' AND entity_id=? AND platform='telegram'", (sid,))
    db.log("short", sid, "telegram", "requeued_after_fix", "link-режим")


def _copy_db(src: str) -> str:
    """Копия БД (вместе с WAL) для dry-run: правим копию, боевую не трогаем."""
    import sqlite3
    import tempfile

    src_path = Path(src)
    dst = Path(tempfile.mkdtemp(prefix="fix_error_rows_")) / src_path.name
    origin = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    try:
        with sqlite3.connect(dst) as target:
            origin.backup(target)
    finally:
        origin.close()
    return str(dst)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="data/data.sqlite")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--youtube", default="399,400",
                    help="id шортсов, чьи YouTube-посты проверить (пусто = все error-строки)")
    ap.add_argument("--telegram", default="270,399,400",
                    help="id шортсов, чьи Telegram-посты вернуть в очередь")
    ap.add_argument("--link", action="append", default=[], metavar="ID=URL",
                    help="точная ссылка YouTube для youtube-строки шортса (можно несколько; "
                         "нужно там, где Postiz ссылку не отдал)")
    ap.add_argument("--commit", action="store_true", help="записать изменения (по умолчанию dry-run)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.commit:
        db_path, mode = args.db, f"ЗАПИСЬ в {args.db}"
    else:
        db_path = _copy_db(args.db)
        mode = f"dry-run на копии {args.db} (боевая БД не меняется)"
    db = Database(db_path)
    clock = SystemClock()
    postiz = HttpPostizClient()
    print(f"БД: {db_path}   режим: {mode}")

    yt_ids = _ids(args.youtube)
    tg_ids = _ids(args.telegram)
    links: dict[int, str] = {}
    for item in args.link:
        sid_raw, _, url = str(item).partition("=")
        sid_raw, url = sid_raw.strip(), url.strip()
        if not sid_raw.isdigit() or not url.startswith("http"):
            print(f"  --link {item!r}: ожидается ID=https://... — пропускаю")
            continue
        links[int(sid_raw)] = url
    scope = yt_ids + tg_ids + list(links)
    before = _snapshot(db, scope)

    print("\n1) Причины ошибок из Postiz (StatusSync)")
    sync = StatusSync(db, postiz, clock, cfg)
    try:
        touched = sync.sync()
        print(f"  StatusSync обработал строк: {touched}")
    except Exception as e:  # noqa: BLE001 — без синхронизации остальную починку делаем
        print(f"  StatusSync не смог отработать: {e}")

    if links:
        print("\n2) Точные ссылки YouTube (из YouTube API, Postiz их не отдал)")
        apply_links(db, links, args.commit)

    print("\n3) Возврат Telegram-постов в очередь (link-режим)")
    for sid in tg_ids:
        requeue_telegram(db, postiz, sid, args.commit)

    after = _snapshot(db, scope)
    still = [k for k, v in after.items()
             if k[2] == "youtube" and v["status"] == "error"
             and (not yt_ids or k[1] in yt_ids)]

    print("\nИзменения по YouTube/Telegram-строкам:")
    if not _show_diff(before, _snapshot(db, scope)):
        print("  нет")
    for k in still:
        print(f"  ВНИМАНИЕ: short {k[1]} [youtube] всё ещё error: {after[k]['last_error']!r}")
        print("      (Postiz не отдал причину — проверьте доступность API и повторите)")

    print("\nДальше (рабочий цикл сам, в течение пары минут):")
    print("  refresh_telegram_links → send_due_telegram_posts: пост-ссылка уйдёт в канал;")
    print("  если у YouTube-поста ссылки нет, пост уйдёт с плейсхолдером "
          "после link_update.release_url_timeout_min.")
    if not args.commit:
        print(f"\nЭто был dry-run на копии БД ({db_path}). В боевой базе изменений нет.")
        print("Для записи повторите с --commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
