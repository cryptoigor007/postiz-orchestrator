from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .config import AppConfig
from .db import Database

logger = logging.getLogger(__name__)


def run_backup(db: Database, cfg: AppConfig, backup_dir: str | Path) -> Path | None:
    if not cfg.backup.enabled:
        return None
    backup_dir = Path(backup_dir)
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        # проверяем, что путь реально доступен на запись (иначе — откат к папке рядом с БД)
        if not os.access(backup_dir, os.W_OK):
            raise PermissionError(str(backup_dir))
    except OSError:
        alt = Path(db.path).resolve().parent / "backups"
        try:
            alt.mkdir(parents=True, exist_ok=True)
            if not os.access(alt, os.W_OK):
                raise PermissionError(str(alt))
            logger.warning("Backup dir %s недоступен — использую %s", backup_dir, alt)
            backup_dir = alt
        except OSError:
            logger.warning("Backup пропущен: нет доступной папки для %s", db.path)
            return None
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    dest = backup_dir.resolve() / f"data_{ts}.sqlite"
    # 10.1: use sqlite3 backup API (no SQL string with path)
    try:
        dest_s = str(dest)
        if any(c in dest_s for c in ("\x00", "\n", "\r")):
            raise ValueError(f"unsafe backup path: {dest_s!r}")
        with sqlite3.connect(db.path) as src:
            with sqlite3.connect(dest_s) as dst:
                src.backup(dst)
        logger.info("Backup created: %s", dest)
        mirror = os.getenv("ORCH_BACKUP_MIRROR", "").strip()
        if mirror:
            try:
                mdir = Path(mirror)
                mdir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, mdir / dest.name)
                _cleanup(mdir, cfg.backup.keep_days)
                logger.info("Backup mirrored: %s", mdir / dest.name)
            except Exception:
                logger.exception("Backup mirror failed")
        _cleanup(backup_dir, cfg.backup.keep_days)
        # гигиена журнала: старые записи publish_log не нужны
        try:
            with sqlite3.connect(db.path) as c:
                cur = c.execute(
                    "DELETE FROM publish_log WHERE created_at < datetime('now', '-90 day')")
                if cur.rowcount:
                    logger.info("publish_log pruned: %s rows", cur.rowcount)
        except Exception:
            logger.exception("publish_log prune failed")
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
