#!/usr/bin/env python3
"""Очистка легаси Telegram-заглушек: если YouTube-видео ещё не вышло, а для
Telegram уже существует Postiz-пост (плейсхолдер «ссылка появится…») — удаляем
этот пост, а строку переводим в 'ready' (waiting_for_youtube). После выхода
видео refresh_telegram_links создаст пост с реальной ссылкой.

Запуск на сервере:
    /opt/orchestrator/venv/bin/python /opt/orchestrator/scripts/cleanup_telegram_placeholders.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from orchestrator.db import Database  # noqa: E402
from orchestrator.postiz_factory import create_postiz_client  # noqa: E402


def main() -> int:
    db_path = os.environ.get("ORCH_DB", "/opt/orchestrator/data/data.sqlite")
    db = Database(db_path)
    postiz = create_postiz_client(dry_run=False)
    rows = db.fetchall(
        """
        SELECT t.entity_type, t.entity_id, t.postiz_post_id
        FROM entity_platform_status t
        JOIN entity_platform_status y
          ON y.entity_type = t.entity_type AND y.entity_id = t.entity_id
         AND y.platform = 'youtube'
        WHERE t.platform = 'telegram'
          AND t.postiz_post_id IS NOT NULL AND t.postiz_post_id != ''
          AND (y.release_url IS NULL OR y.release_url = '')
        """
    )
    removed = skipped = 0
    for r in rows:
        pid = r["postiz_post_id"]
        post = postiz.get_post(pid)
        if post is None:
            db.execute(
                "UPDATE entity_platform_status SET postiz_post_id=NULL, status='ready', "
                "last_error='waiting_for_youtube' WHERE entity_type=? AND entity_id=? "
                "AND platform='telegram'",
                (r["entity_type"], r["entity_id"]),
            )
            removed += 1
            print(f"  {r['entity_type']}/{r['entity_id']}: пост {pid} уже отсутствует — строка в ready")
            continue
        if (post.status or "").lower() == "published":
            skipped += 1
            print(f"  {r['entity_type']}/{r['entity_id']}: пост {pid} уже опубликован — пропускаю")
            continue
        postiz.delete_post(pid)
        db.execute(
            "UPDATE entity_platform_status SET postiz_post_id=NULL, status='ready', "
            "last_error='waiting_for_youtube' WHERE entity_type=? AND entity_id=? "
            "AND platform='telegram'",
            (r["entity_type"], r["entity_id"]),
        )
        removed += 1
        print(f"  {r['entity_type']}/{r['entity_id']}: заглушка {pid} удалена -> ready")
    print(f"ИТОГ: удалено {removed}, пропущено (уже опубликованы) {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
