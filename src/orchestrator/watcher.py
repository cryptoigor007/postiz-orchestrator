from __future__ import annotations

import json
import logging
from pathlib import Path

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

    def _platform_map(self, base: Path, platforms: list[str]) -> dict[str, str]:
        """Карта платформ -> файл: base/<platform>/*.mp4 или base/<platform>.mp4."""
        out: dict[str, str] = {}
        for p in platforms:
            d = base / p
            if d.is_dir():
                f = next((x for x in sorted(d.glob("*.mp4"))), None)
                if f:
                    out[p] = str(f.resolve())
                continue
            f = base / f"{p}.mp4"
            if f.is_file():
                out[p] = str(f.resolve())
        return out

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            return ""

    def _meta_kv(self, path: Path) -> dict[str, str]:
        out: dict[str, str] = {}
        for line in self._read_text(path).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip().lower(), v.strip()
                if k and v:
                    out.setdefault(k, v)
        return out

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
            # root сам может быть серией (vertical/wide внутри)
            if (root / "vertical").is_dir() or (root / "wide").is_dir():
                stats["long"] += self._scan_long(root)
                stats["shorts"] += self._scan_shorts(root)
            for series in root.iterdir():
                if not series.is_dir() or series.name.startswith("."):
                    continue
                if "shorts_overflow" in series.name:
                    continue
                stats["long"] += self._scan_long(series)
                stats["shorts"] += self._scan_shorts(series)
        return stats

    def _scan_long(self, series: Path) -> int:
        platforms = list(self.cfg.platforms.keys())
        pmap = self._platform_map(series, platforms)
        wide = series / "wide" / "final_16x9.mp4"
        vert = series / "vertical" / "final_9x16.mp4"
        if not wide.exists() and not vert.exists() and not pmap:
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
        meta_kv = self._meta_kv(series / "info_metadata.txt")
        title_text = meta_kv.get("package_title") or self._read_text(
            series / "info_metadata.txt"
        )[:200]
        desc_text = (
            self._read_text(series / "vertical" / f"{series.name}_description.txt")
            or self._read_text(series / "wide" / f"{series.name}_description.txt")
        )
        tags_text = (
            meta_kv.get("package_hashtags")
            or self._read_text(series / "vertical" / f"{series.name}_hashtags.txt")
            or self._read_text(series / "wide" / f"{series.name}_hashtags.txt")
        )

        now = self.clock.now().isoformat()
        self.db.execute(
            """
            INSERT INTO long_videos
                (source, folder_path, title, wide_path, vertical_path,
                 title_text, description_text, hashtags_text, platform_paths, created_at)
            VALUES ('videomaker', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                folder, title,
                str(wide) if wide.exists() else None,
                str(vert) if vert.exists() else None,
                title_text, desc_text, tags_text,
                (json.dumps(pmap) if pmap else None), now,
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
        platforms = list(self.cfg.platforms.keys())
        for i, short_dir in enumerate(sorted(shorts_dir.iterdir())):
            if not short_dir.is_dir():
                continue
            pmap = self._platform_map(short_dir, platforms)
            generic = [f for f in sorted(short_dir.glob("*.mp4")) if f.stem not in platforms]
            if generic:
                video = generic[0]
            elif pmap:
                video = Path(next(iter(pmap.values())))
            else:
                video = None
            if not video or not self._is_stable(video):
                continue
            folder = str(short_dir.resolve())
            if self.db.fetchone("SELECT id FROM shorts WHERE folder_path = ?", (folder,)):
                continue
            name = short_dir.name
            title_text = self._read_text(short_dir / f"{name}_title.txt") or name
            desc_text = self._read_text(short_dir / f"{name}_description.txt")
            tags_text = self._read_text(short_dir / f"{name}_hashtags.txt")
            hook_text = self._read_text(short_dir / f"{name}_hook.txt")
            upload_text = self._read_text(short_dir / f"{name}_upload.txt")
            cover = next(short_dir.glob("cover*"), None) or next(
                short_dir.glob("*_cover.*"), None
            )
            now = self.clock.now().isoformat()
            self.db.execute(
                """
                INSERT INTO shorts
                    (source, parent_video_id, folder_path, order_index,
                     video_path, cover_path, title_text, description_text,
                     hashtags_text, hook_text, upload_text, platform_paths, created_at)
                VALUES ('videomaker', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parent_id, folder, i,
                    str(video), str(cover) if cover else None,
                    title_text, desc_text, tags_text,
                    hook_text, upload_text,
                    (json.dumps(pmap) if pmap else None), now,
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
