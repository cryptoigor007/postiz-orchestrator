#!/usr/bin/env python3
"""Очистка легаси Telegram-заглушек без platform-клиента.

Если YouTube-видео ещё не вышло (нет release_url), а для Telegram в EPS
есть legacy legacy_post_id / external_id плейсхолдер — переводим строку
в ready / waiting_for_youtube. Реальный refresh_telegram_links создаст
пост с реальной ссылкой после премьеры.

Запуск:
    PYTHONPATH=src python3 scripts/cleanup_telegram_placeholders.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from orchestrator.db import Database  # noqa: E402


def main() -> int:
    db_path = os.environ.get("ORCH_DB", "data/data.sqlite")
    db = Database(db_path)
    rows = db.fetchall(
        """
        SELECT t.entity_type, t.entity_id,
               COALESCE(t.external_id, t.legacy_post_id) AS eid
        FROM entity_platform_status t
        JOIN entity_platform_status y
          ON y.entity_type = t.entity_type AND y.entity_id = t.entity_id
         AND y.platform = 'youtube'
        WHERE t.platform = 'telegram'
          AND (
                (t.legacy_post_id IS NOT NULL AND t.legacy_post_id != '')
             OR (t.external_id IS NOT NULL AND t.external_id != '')
          )
          AND (y.release_url IS NULL OR y.release_url = '')
          AND t.status NOT IN ('published', 'publishing')
        """
    )
    removed = 0
    for r in rows:
        db.execute(
            "UPDATE entity_platform_status SET legacy_post_id=NULL, external_id=NULL, "
            "status='ready', last_error='waiting_for_youtube' "
            "WHERE entity_type=? AND entity_id=? AND platform='telegram'",
            (r["entity_type"], r["entity_id"]),
        )
        removed += 1
        print(
            f"  {r['entity_type']}/{r['entity_id']}: placeholder {r['eid']} cleared -> ready"
        )
    print(f"ИТОГ: очищено {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
