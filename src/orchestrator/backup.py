from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import logging
import sqlite3

from .config import AppConfig
from .db import Database

logger = logging.getLogger(__name__)


def run_backup(db: Database, cfg: AppConfig, backup_dir: str | Path) -> Path | None:
    if not cfg.backup.enabled:
        return None
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"data_{ts}.sqlite"
    # VACUUM INTO is safe online backup for SQLite
    try:
        with sqlite3.connect(db.path) as src:
            src.execute(f"VACUUM INTO '{dest}'")
        logger.info("Backup created: %s", dest)
        _cleanup(backup_dir, cfg.backup.keep_days)
        return dest
    except Exception as e:
        logger.error("Backup failed: %s", e)
        return None


def _cleanup(backup_dir: Path, keep_days: int) -> None:
    import time
    cutoff = time.time() - keep_days * 86400
    for f in backup_dir.glob("data_*.sqlite"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
            logger.info("Removed old backup %s", f)
