from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json
import logging
import os

from .clock import Clock
from .config import AppConfig
from .db import Database

logger = logging.getLogger(__name__)

WATCH_ROOTS_KEY = "watch_roots"


class Watcher:
    def __init__(self, db: Database, cfg: AppConfig, clock: Clock, roots: list[str],
                 max_age_days: int = 30):
        self.db = db
        self.cfg = cfg
        self.clock = clock
        self.roots = [Path(r) for r in roots]
        self.max_age_days = max_age_days
        self._size_cache: dict[str, tuple[int, int]] = {}

    def effective_roots(self) -> list[Path]:
        """Roots configured via webapp (DB) take precedence over CLI defaults."""
        raw = self.db.get_setting(WATCH_ROOTS_KEY)
        if raw:
            try:
                items = json.loads(raw)
                if isinstance(items, list) and items:
                    return [Path(str(x)) for x in items]
            except Exception:
                logger.warning("Invalid %s setting", WATCH_ROOTS_KEY)
        return list(self.roots)

    def _is_fresh_enough(self, path: Path) -> bool:
        if self.max_age_days <= 0:
            return True
        try:
            import time
            age = time.time() - path.stat().st_mtime
            return age <= self.max_age_days * 86400
        except OSError:
            return False

    def _is_stable(self, path: Path) -> bool:

        try:
            size = path.stat().st_size
        except OSError:
            return False
        key = str(path)
        prev = self._size_cache.get(key)
        if prev and prev[0] == size:
            cycles = prev[1] + 1
            self._size_cache[key] = (size, cycles)
            return cycles >= self.cfg.file_stability_cycles
        self._size_cache[key] = (size, 1)
        return False

    def scan(self) -> dict[str, int]:
        stats = {"long": 0, "shorts": 0, "standalone": 0}
        for root in self.effective_roots():
            if not root.exists():
                continue
            # shortsmaker root: flat or dated folders with mp4
            if root.name.lower().startswith("shortsmaker") or (root / ".shortsmaker").exists():
                stats["standalone"] += self._scan_standalone_root(root)
                continue
            for series in root.iterdir():
                if not series.is_dir() or series.name.startswith("."):
                    continue
                if "shorts_overflow" in series.name:
                    continue
                stats["long"] += self._scan_long(series)
                stats["shorts"] += self._scan_shorts(series)
        return stats

    def _scan_long(self, series: Path) -> int:
        wide = series / "wide" / "final_16x9.mp4"
        vert = series / "vertical" / "final_9x16.mp4"
        if not wide.exists() and not vert.exists():
            return 0
        # stability on existing files
        for p in (wide, vert):
            if p.exists() and not self._is_stable(p):
                return 0

        folder = str(series.resolve())
        existing = self.db.fetchone(
            "SELECT id FROM long_videos WHERE folder_path = ?", (folder,)
        )
        if existing:
            return 0

        title = series.name
        meta = series / "info_metadata.txt"
        title_text = desc = tags = ""
        if meta.exists():
            text = meta.read_text(encoding="utf-8", errors="ignore")
            title_text = text[:200]

        now = self.clock.now().isoformat()
        self.db.execute(
            """
            INSERT INTO long_videos
                (source, folder_path, title, wide_path, vertical_path,
                 title_text, description_text, hashtags_text, created_at)
            VALUES ('videomaker', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                folder, title,
                str(wide) if wide.exists() else None,
                str(vert) if vert.exists() else None,
                title_text, desc, tags, now,
            ),
        )
        logger.info("Registered long video: %s", folder)
        return 1

    def _scan_shorts(self, series: Path) -> int:
        shorts_dir = series / "shorts"
        if not shorts_dir.is_dir():
            return 0
        parent = self.db.fetchone(
            "SELECT id FROM long_videos WHERE folder_path = ?",
            (str(series.resolve()),),
        )
        parent_id = parent["id"] if parent else None
        count = 0
        for i, short_dir in enumerate(sorted(shorts_dir.iterdir())):
            if not short_dir.is_dir():
                continue
            video = next(short_dir.glob("*.mp4"), None)
            if not video or not self._is_stable(video):
                continue
            folder = str(short_dir.resolve())
            if self.db.fetchone("SELECT id FROM shorts WHERE folder_path = ?", (folder,)):
                continue
            cover = next(short_dir.glob("cover*"), None)
            now = self.clock.now().isoformat()
            self.db.execute(
                """
                INSERT INTO shorts
                    (source, parent_video_id, folder_path, order_index,
                     video_path, cover_path, title_text, description_text,
                     hashtags_text, created_at)
                VALUES ('videomaker', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parent_id, folder, i,
                    str(video), str(cover) if cover else None,
                    short_dir.name, "", "", now,
                ),
            )
            count += 1
        return count

    def _scan_standalone_root(self, root: Path) -> int:
        """ShortsMaker: any subfolder with *.mp4, or loose mp4 files."""
        count = 0
        candidates = []
        for p in root.rglob("*.mp4"):
            if "overflow" in str(p):
                continue
            candidates.append(p)
        for video in candidates:
            if not self._is_stable(video) or not self._is_fresh_enough(video):
                continue
            folder = str(video.parent.resolve())
            if self.db.fetchone("SELECT id FROM shorts WHERE folder_path = ?", (folder,)):
                continue
            # skip if looks like videomaker short under series/shorts/
            if video.parent.name.startswith("short_") and (video.parent.parent.name == "shorts"):
                continue
            now = self.clock.now().isoformat()
            self.db.execute(
                """
                INSERT INTO shorts
                    (source, parent_video_id, folder_path, order_index,
                     video_path, title_text, description_text, hashtags_text, created_at)
                VALUES ('shortsmaker', NULL, ?, 0, ?, ?, '', '', ?)
                """,
                (folder, str(video), video.stem, now),
            )
            count += 1
            logger.info("Registered standalone short: %s", video)
        return count
