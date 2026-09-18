from __future__ import annotations
from collections import defaultdict
from datetime import datetime

from .db import Database


def build_calendar(db: Database, limit_days: int = 30) -> str:
    rows = db.fetchall(
        """
        SELECT platform, postiz_scheduled_for, entity_type, entity_id, status
        FROM entity_platform_status
        WHERE postiz_scheduled_for IS NOT NULL
        ORDER BY postiz_scheduled_for
        LIMIT 500
        """
    )
    by_day: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        day = r["postiz_scheduled_for"][:10]
        by_day[day].append(
            f"  {r['postiz_scheduled_for'][11:16]} {r['platform']} "
            f"{r['entity_type']}#{r['entity_id']} [{r['status']}]"
        )
    if not by_day:
        return "Calendar empty"
    lines = []
    for day in sorted(by_day.keys())[:limit_days]:
        lines.append(day)
        lines.extend(by_day[day])
    return "\n".join(lines)
