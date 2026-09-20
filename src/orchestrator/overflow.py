from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .clock import Clock
from .config import AppConfig
from .db import Database

logger = logging.getLogger(__name__)


def move_excess_shorts(
    db: Database,
    cfg: AppConfig,
    clock: Clock,
    parent_video_id: int,
) -> int:
    """Move shorts beyond max_shorts_per_long_video into shorts_overflow/ and mark skipped."""
    max_n = cfg.limits.max_shorts_per_long_video
    shorts = db.fetchall(
        "SELECT id, folder_path FROM shorts WHERE parent_video_id=? ORDER BY order_index, id",
        (parent_video_id,),
    )
    if len(shorts) <= max_n:
        return 0
    excess = shorts[max_n:]
    moved = 0
    for s in excess:
        src = Path(s["folder_path"])
        if not src.exists():
            continue
        move_files = bool(getattr(cfg.limits, "overflow_move_files", False))
        if move_files:
            # series root = parent of shorts/
            series = src.parent.parent if src.parent.name == "shorts" else src.parent
            overflow = series / "shorts_overflow" / src.name
            overflow.parent.mkdir(parents=True, exist_ok=True)
            if not overflow.exists():
                shutil.move(str(src), str(overflow))
        for platform in cfg.platforms:
            db.execute(
                """
                INSERT INTO entity_platform_status
                    (entity_type, entity_id, platform, status, last_error)
                VALUES ('short', ?, ?, 'skipped', 'overflow')
                ON CONFLICT(entity_type, entity_id, platform) DO UPDATE SET
                    status='skipped', last_error='overflow'
                """,
                (s["id"], platform),
            )
        db.log("short", s["id"], None,
               "overflow_moved" if move_files else "overflow_skipped", "")
        moved += 1
        if move_files:
            logger.info("Moved excess short %s -> %s", src, overflow)
        else:
            logger.info("Excess short skipped (files kept): %s", src)
    return moved
