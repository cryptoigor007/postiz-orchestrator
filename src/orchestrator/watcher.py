from __future__ import annotations

import json
import logging
import unicodedata
from pathlib import Path

from .clock import Clock
from .config import AppConfig
from .db import Database

logger = logging.getLogger(__name__)

WATCH_ROOTS_KEY = "watch_roots"

JUNK_DIR_NAMES = {
    "$RECYCLE.BIN",
    "System Volume Information",
    "__pycache__",
    # архивы/бэкапы/исходники — не публикуем:
    "broll_downloads",
    "BACKUP_PVE",
    "ютюб",
    "нотика",
    "кальянная херь",
    "записи игоря криптостратегия",
}
JUNK_SUBSTR = ("shorts_overflow",)
META_MARKERS = ("_titles.txt", "_title.txt", "_hashtags.txt", "_hooks.txt")


class Watcher:
    def __init__(self, db: Database, cfg: AppConfig, clock: Clock, roots: list[str],
                 max_age_days: int = 3650):
        self.db = db
        self.cfg = cfg
        self.clock = clock
        self.roots = [Path(r) for r in roots]
        self.max_age_days = max_age_days
        self._size_cache: dict[str, tuple[int, int]] = {}

    def effective_root_specs(self) -> list[dict[str, str]]:
        """Корни с типами: [{"path": ..., "kind": auto|series|shorts}] (legacy-строки → auto)."""
        raw = self.db.get_setting(WATCH_ROOTS_KEY)
        specs: list[dict[str, str]] = []
        if raw:
            try:
                items = json.loads(raw)
            except Exception:
                items = None
                logger.warning("Invalid %s setting", WATCH_ROOTS_KEY)
            if isinstance(items, list):
                for x in items:
                    if isinstance(x, dict):
                        path = str(x.get("path") or "").strip()
                        kind = str(x.get("kind") or "auto").strip().lower()
                        if path:
                            specs.append({"path": path, "kind": kind if kind in ("auto", "series", "shorts") else "auto"})
                    elif isinstance(x, (str, Path)):
                        specs.append({"path": str(x), "kind": "auto"})
        if specs:
            return specs
        return [{"path": str(r), "kind": "auto"} for r in self.roots]

    def effective_roots(self) -> list[Path]:
        """Roots configured via webapp (DB) take precedence over CLI defaults."""
        return [Path(spec["path"]) for spec in self.effective_root_specs()]

    # ---------- helpers ----------

    def _read_first(self, base: Path, names: list[str], suffix: str) -> str:
        for n in names:
            txt = self._read_text(base / f"{n}{suffix}")
            if txt:
                return txt
        return ""

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

    def _clean_name(self, name: str) -> str:
        cleaned = "".join(ch for ch in name if unicodedata.category(ch) != "Co").strip()
        return cleaned or name

    def _first_field(self, text: str, field: str) -> str:
        prefix = field.lower() + ":"
        for line in text.splitlines():
            s = line.strip()
            if s.lower().startswith(prefix):
                return s.split(":", 1)[1].strip()
        return ""

    def _first_hook(self, text: str) -> str:
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("---") or s.lower().startswith("вариант"):
                continue
            return s
        return ""

    def _is_junk_dir(self, name: str) -> bool:
        if name.startswith(".") or name.startswith("_"):
            return True
        if name in JUNK_DIR_NAMES or name.endswith(".app"):
            return True
        return any(s in name for s in JUNK_SUBSTR)

    def _mp4s(self, d: Path) -> list[Path]:
        if not d.is_dir():
            return []
        return [p for p in sorted(d.glob("*.mp4")) if not p.name.startswith("._")]

    def _first_mp4(self, d: Path) -> Path | None:
        files = self._mp4s(d)
        if not files:
            return None
        for p in files:
            if "final" in p.stem:
                return p
        return files[0]

    def _platform_map(self, base: Path, platforms: list[str]) -> dict[str, str]:
        """Карта платформ -> файл: base/<platform>/*.mp4 или base/<platform>.mp4."""
        out: dict[str, str] = {}
        for p in platforms:
            d = base / p
            if d.is_dir():
                f = self._first_mp4(d)
                if f:
                    out[p] = str(f.resolve())
                continue
            f = base / f"{p}.mp4"
            if f.is_file():
                out[p] = str(f.resolve())
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
        """R2: require size stable across two stats to reduce race with writers."""
        try:
            size = path.stat().st_size
        except OSError:
            return False
        key = str(path)
        prev = self._size_cache.get(key)
        if prev and prev[0] == size:
            cycles = prev[1] + 1
            self._size_cache[key] = (size, cycles)
            if len(self._size_cache) > 10000:
                self._size_cache.clear()
            return cycles >= self.cfg.file_stability_cycles
        self._size_cache[key] = (size, 1)
        if len(self._size_cache) > 10000:
            self._size_cache.clear()
        return False

    # ---------- scan ----------

    def _link_orphan_shorts(self) -> int:
        """Восстанавливает parent_video_id у шортсов, чьи серии уже есть в БД."""
        before = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM shorts WHERE parent_video_id IS NULL")
        self.db.execute(
            """
            UPDATE shorts SET parent_video_id = (
                SELECT lv.id FROM long_videos lv
                WHERE shorts.folder_path LIKE lv.folder_path || '/shorts/%'
            )
            WHERE parent_video_id IS NULL
              AND EXISTS (
                SELECT 1 FROM long_videos lv
                WHERE shorts.folder_path LIKE lv.folder_path || '/shorts/%'
              )
            """
        )
        after = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM shorts WHERE parent_video_id IS NULL")
        return max(0, (before or {}).get("c", 0) - (after or {}).get("c", 0))

    def scan(self) -> dict[str, int]:
        stats = {"long": 0, "shorts": 0, "standalone": 0}
        max_depth = getattr(self.cfg, "watch_max_depth", 5)
        for spec in self.effective_root_specs():
            root = Path(spec["path"])
            mode = spec.get("kind", "auto")
            if not root.exists():
                continue
            if root.name.lower().startswith("shortsmaker") or (root / ".shortsmaker").exists():
                if mode != "series":
                    stats["standalone"] += self._scan_standalone_root(root)
                continue
            self._walk(root, 0, max_depth, stats, mode)
        linked = self._link_orphan_shorts()
        if linked:
            logger.info("Linked orphan shorts to series: %s", linked)
        filled = self._backfill_descriptions()
        if filled:
            logger.info("Backfilled descriptions: %s", filled)
        return stats

    def _backfill_descriptions(self) -> int:
        """Дозаполняет пустые описания из файлов *_description.txt рядом с видео."""
        n = 0
        rows = self.db.fetchall(
            "SELECT id, video_path FROM shorts "
            "WHERE (description_text IS NULL OR description_text='') AND video_path IS NOT NULL")
        for r in rows:
            vp = Path(r["video_path"])
            cand = vp.with_name(vp.stem + "_description.txt")
            text = self._read_text(cand)
            if text:
                self.db.execute("UPDATE shorts SET description_text=? WHERE id=?",
                                (text, r["id"]))
                n += 1
        rows = self.db.fetchall(
            "SELECT id, folder_path FROM long_videos "
            "WHERE (description_text IS NULL OR description_text='') AND folder_path IS NOT NULL")
        for r in rows:
            folder = Path(r["folder_path"])
            name = folder.name
            text = (self._read_text(folder / "vertical" / f"{name}_description.txt")
                    or self._read_text(folder / "wide" / f"{name}_description.txt"))
            if text:
                self.db.execute("UPDATE long_videos SET description_text=? WHERE id=?",
                                (text, r["id"]))
                n += 1
        return n

    def _walk(self, d: Path, depth: int, max_depth: int, stats: dict[str, int],
              mode: str = "auto") -> None:
        if depth > max_depth:
            return
        if self._is_episode(d):
            if mode != "shorts":
                stats["long"] += self._scan_long(d)
                stats["shorts"] += self._scan_shorts(d)
            else:
                stats["standalone"] += self._scan_shorts(d, with_parent=False)
            return
        if mode != "series":
            if self._register_shorts_maker_short(d):
                stats["standalone"] += 1
                return
            loose = self._register_loose_shorts(d)
            if loose:
                stats["standalone"] += loose
                return
        for child in sorted(d.iterdir()):
            if not child.is_dir() or self._is_junk_dir(child.name):
                continue
            self._walk(child, depth + 1, max_depth, stats, mode)

    def _is_episode(self, d: Path) -> bool:
        if (d / "vertical").is_dir() or (d / "wide").is_dir():
            return True
        platforms = list(self.cfg.platforms.keys())
        return bool(self._platform_map(d, platforms))

    def _scan_long(self, series: Path) -> int:
        platforms = list(self.cfg.platforms.keys())
        pmap = self._platform_map(series, platforms)
        wide = self._first_mp4(series / "wide")
        vert = self._first_mp4(series / "vertical")
        if not wide and not vert and not pmap:
            return 0
        for p in (wide, vert):
            if p and not self._is_stable(p):
                return 0

        folder = str(series.resolve())
        existing = self.db.fetchone(
            "SELECT id FROM long_videos WHERE folder_path = ?", (folder,)
        )
        if existing:
            return 0
        cover = next(series.glob("cover*"), None) or next(series.glob("*_cover.*"), None)
        if cover is None:
            cover = next((series / "wide").glob("*cover*"), None) if (series / "wide").is_dir() else None

        title = self._clean_name(series.name)
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
                 title_text, description_text, hashtags_text, platform_paths, cover_path,
                 created_at)
            VALUES ('videomaker', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                folder, title,
                str(wide) if wide else None,
                str(vert) if vert else None,
                title_text, desc_text, tags_text,
                (json.dumps(pmap) if pmap else None),
                str(cover) if cover else None, now,
            ),
        )
        logger.info("Registered long video: %s", folder)
        return 1

    def _scan_shorts(self, series: Path, with_parent: bool = True) -> int:
        shorts_dir = series / "shorts"
        if not shorts_dir.is_dir():
            return 0
        parent = self.db.fetchone(
            "SELECT id FROM long_videos WHERE folder_path = ?",
            (str(series.resolve()),),
        ) if with_parent else None
        parent_id = parent["id"] if parent else None
        count = 0
        platforms = list(self.cfg.platforms.keys())
        for i, short_dir in enumerate(sorted(shorts_dir.iterdir())):
            if not short_dir.is_dir() or self._is_junk_dir(short_dir.name):
                continue
            pmap = self._platform_map(short_dir, platforms)
            generic = [f for f in self._mp4s(short_dir) if f.stem not in platforms]
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
            # имя файлов-компаньонов: по basename видео, затем по имени папки
            # (папки вида short_001выст, где файлы названы short_001_*)
            name = video.stem or short_dir.name
            names = [name] if short_dir.name == name else [name, short_dir.name]
            title_text = (self._read_first(short_dir, names, "_title.txt")
                          or self._clean_name(name))
            desc_text = self._read_first(short_dir, names, "_description.txt")
            tags_text = self._read_first(short_dir, names, "_hashtags.txt")
            hook_text = self._read_first(short_dir, names, "_hook.txt")
            upload_text = self._read_first(short_dir, names, "_upload.txt")
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

    def _register_shorts_maker_short(self, d: Path) -> bool:
        """Папка одного шортса Shorts Maker: *_final.mp4 + мета-файлы рядом."""
        files = self._mp4s(d)
        if not files:
            return False
        final = next((p for p in files if "_final" in p.stem), None)
        if not final:
            return False
        metas = [p for p in d.iterdir() if p.is_file() and p.name.endswith(META_MARKERS)]
        if not metas:
            return False
        folder = str(d.resolve())
        if self.db.fetchone("SELECT id FROM shorts WHERE folder_path = ?", (folder,)):
            return True
        if not self._is_stable(final) or not self._is_fresh_enough(final):
            return True
        prefix = final.stem[: -len("_final")] if final.stem.endswith("_final") else final.stem
        titles_text = self._read_text(d / f"{prefix}_titles.txt") or self._read_text(
            d / f"{prefix}_title.txt"
        )
        hooks_text = self._read_text(d / f"{prefix}_hooks.txt")
        tags_text = self._read_text(d / f"{prefix}_hashtags.txt")
        title_text = self._first_field(titles_text, "Заголовок") or self._clean_name(d.name)
        desc_text = (self._read_text(d / f"{prefix}_description.txt")
                     or self._first_field(titles_text, "Описание"))
        hook_text = self._first_hook(hooks_text)
        tags_line = tags_text.splitlines()[0].strip() if tags_text else ""
        cover = next(d.glob("*_final_cover.*"), None) or next(d.glob("*cover*"), None)
        now = self.clock.now().isoformat()
        self.db.execute(
            """
            INSERT INTO shorts
                (source, parent_video_id, folder_path, order_index,
                 video_path, cover_path, title_text, description_text,
                 hashtags_text, hook_text, upload_text, platform_paths, created_at)
            VALUES ('shortsmaker', NULL, ?, 0, ?, ?, ?, ?, ?, ?, '', NULL, ?)
            """,
            (
                folder, str(final), str(cover) if cover else None,
                title_text, desc_text, tags_line, hook_text, now,
            ),
        )
        logger.info("Registered Shorts Maker clip: %s", folder)
        return True

    def _register_loose_shorts(self, d: Path) -> int:
        """Отдельные mp4 с мета-файлами рядом (stem совпадает с префиксом меты)."""
        files = self._mp4s(d)
        if not files:
            return 0
        metas = [p.name for p in d.iterdir() if p.is_file() and p.name.endswith(META_MARKERS)]
        if not metas:
            return 0
        count = 0
        for video in files:
            stem = video.stem
            mine = [m for m in metas if m.startswith(stem)]
            if not mine:
                continue
            if not self._is_stable(video) or not self._is_fresh_enough(video):
                continue
            key = f"{d.resolve()}::{video.name}"
            if self.db.fetchone("SELECT id FROM shorts WHERE folder_path = ?", (key,)):
                continue
            def pick(suffix: str, mine: tuple[str, ...] = tuple(mine)) -> str:
                for m in mine:
                    if m.endswith(suffix):
                        return self._read_text(d / m)
                return ""
            titles_text = pick("_titles.txt") or pick("_title.txt")
            title_text = (
                self._first_field(titles_text, "Заголовок")
                or pick("_title.txt")
                or self._clean_name(stem)
            )
            desc_text = pick("_description.txt") or self._first_field(titles_text, "Описание")
            hook_text = self._first_hook(pick("_hooks.txt"))
            tags = pick("_hashtags.txt").splitlines()
            cover = next(d.glob(f"{stem}*cover*"), None)
            now = self.clock.now().isoformat()
            self.db.execute(
                """
                INSERT INTO shorts
                    (source, parent_video_id, folder_path, order_index,
                     video_path, cover_path, title_text, description_text,
                     hashtags_text, hook_text, upload_text, platform_paths, created_at)
                VALUES ('shortsmaker', NULL, ?, 0, ?, ?, ?, ?, ?, ?, '', NULL, ?)
                """,
                (
                    key, str(video), str(cover) if cover else None,
                    title_text, desc_text, tags[0].strip() if tags else "", hook_text, now,
                ),
            )
            count += 1
        return count

    def _scan_standalone_root(self, root: Path) -> int:
        """ShortsMaker root (маркер .shortsmaker): any subfolder with *.mp4, or loose mp4 files."""
        count = 0
        candidates = []
        for p in root.rglob("*.mp4"):
            if "overflow" in str(p) or p.name.startswith("._"):
                continue
            candidates.append(p)
        for video in candidates:
            if not self._is_stable(video) or not self._is_fresh_enough(video):
                continue
            key = f"{video.parent.resolve()}::{video.name}"
            if self.db.fetchone("SELECT id FROM shorts WHERE folder_path = ?", (key,)):
                continue
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
                (key, str(video), self._clean_name(video.stem), now),
            )
            count += 1
            logger.info("Registered standalone short: %s", video)
        return count
