from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from pathlib import Path

from .clock import Clock
from .config import AppConfig
from .db import Database

logger = logging.getLogger(__name__)


def natural_key(name: str) -> tuple:
    """Ключ сортировки с числами: «ш1 < ш2 < … < ш10» (а не «ш1 < ш10 < ш2»).

    Пробелы и регистр не влияют: «Ш 19 …», «ш1 …», «ш10…» → 1, 2, 10…
    """
    flat = re.sub(r"\s+", "", name).lower()
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part)
        for part in re.split(r"(\d+)", flat) if part
    )

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
# обложки серии: имена произвольные, формат определяем по размерам картинки
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


class Watcher:
    def __init__(self, db: Database, cfg: AppConfig, clock: Clock, roots: list[str],
                 max_age_days: int = 3650):
        self.db = db
        self.cfg = cfg
        self.clock = clock
        self.roots = [Path(r) for r in roots]
        self.max_age_days = max_age_days
        self._size_cache: dict[str, tuple[int, int, int]] = {}
        self._scan_seq = 0  # номер скана: устойчивость подтверждается разными сканами

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
        out: list[Path] = []
        for spec in self.effective_root_specs():
            try:
                out.append(Path(spec["path"]).resolve())
            except OSError:
                logger.warning("watch root недоступен: %s", spec.get("path"))
                out.append(Path(spec["path"]))
        return out

    # ---------- helpers ----------

    def _read_first(self, base: Path, names: list[str], suffix: str) -> str:
        for n in names:
            txt = self._read_text(base / f"{n}{suffix}")
            if txt:
                return txt
        return ""

    def _read_text(self, path: Path) -> str:
        # ._* — служебные AppleDouble-файлы macOS, их содержимое не текст
        if path.name.startswith("._"):
            return ""
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
        return sorted(
            (p for p in d.glob("*.mp4") if not p.name.startswith("._")),
            key=lambda p: natural_key(p.name),
        )

    def _first_mp4(self, d: Path) -> Path | None:
        files = self._mp4s(d)
        if not files:
            return None
        for p in files:
            if "final" in p.stem:
                return p
        return files[0]

    def _final_mp4(self, d: Path) -> Path | None:
        """Только финальный файл: master_* и прочее не берём (стандарт видео мейкера)."""
        if not d.is_dir():
            return None
        for p in sorted(d.glob("*.mp4")):
            if p.name.startswith("._"):
                continue
            if "final" in p.stem:
                return p
        return None

    def _first_cover(self, d: Path) -> Path | None:
        """Обложка в папке (cover*, *_cover.*) — без служебных ._* файлов macOS."""
        for pattern in ("cover*", "*_cover.*"):
            for p in sorted(d.glob(pattern)):
                if (p.is_file() and not p.name.startswith("._")
                        and p.suffix.lower() in IMAGE_EXTS):
                    return p
        return None

    def _package_dirs(self, series: Path) -> dict[str, Path]:
        """Пакеты платформ внутри папки серии: <platform>/{vertical,wide,shorts}."""
        out: dict[str, Path] = {}
        for name in self.cfg.platforms.keys():
            d = series / name
            if d.is_dir() and any((d / sub).is_dir() for sub in ("vertical", "wide", "shorts")):
                out[name] = d
        return out

    def _variant(self, platform: str) -> str:
        """Формат длинного видео для платформы из конфига (wide|vertical)."""
        pcfg = self.cfg.platforms.get(platform)
        variant = str(getattr(pcfg, "video_variant", "wide") or "wide").strip().lower()
        return variant if variant in ("wide", "vertical") else "wide"

    def _platform_map(self, base: Path, platforms: list[str]) -> dict[str, str]:
        """Карта платформ -> файл.
        Пакет платформы: base/<platform>/<её формат>/final_*.mp4 — только свой формат и
        только final (вертикаль внутри youtube/ не берём никому).
        Плоский вид: base/<platform>/*.mp4 или base/<platform>.mp4.
        """
        out: dict[str, str] = {}
        for p in platforms:
            d = base / p
            if d.is_dir():
                variant_dir = d / self._variant(p)
                f = self._final_mp4(variant_dir) if variant_dir.is_dir() else None
                if f is None and not variant_dir.is_dir():
                    f = self._final_mp4(d)  # master_* не публикуем (docs: только final)
                if f:
                    out[p] = str(f.resolve())
                continue
            f = base / f"{p}.mp4"
            if f.is_file():
                out[p] = str(f.resolve())
        return out

    # ---------- обложки серии ----------

    def _series_text(self, series: Path, suffix: str) -> str:
        """<номер>_<suffix>.txt: сначала из пакетов платформ, потом из корня серии."""
        bases = list(self._package_dirs(series).values()) + [series]
        for base in bases:
            for sub in ("vertical", "wide"):
                txt = self._read_first(base / sub, [series.name], f"_{suffix}.txt")
                if txt:
                    return txt
        return ""

    def _image_size(self, path: Path) -> tuple[int, int] | None:
        """Размер картинки (ширина, высота) без внешних библиотек: PNG, JPEG, WebP."""
        try:
            with path.open("rb") as fh:
                head = fh.read(32)
                if len(head) < 16:
                    return None
                if head.startswith(b"\x89PNG\r\n\x1a\n"):
                    return (int.from_bytes(head[16:20], "big"),
                            int.from_bytes(head[20:24], "big"))
                if head.startswith(b"\xff\xd8"):
                    return self._jpeg_size(fh)
                if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                    return self._webp_size(head, fh)
        except OSError:
            return None
        return None

    @staticmethod
    def _jpeg_size(fh) -> tuple[int, int] | None:
        fh.seek(2)
        while True:
            b = fh.read(1)
            while b and b != b"\xff":
                b = fh.read(1)
            marker = fh.read(1)
            while marker == b"\xff":
                marker = fh.read(1)
            if not marker:
                return None
            m = marker[0]
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                continue
            size_bytes = fh.read(2)
            if len(size_bytes) < 2:
                return None
            seg_len = int.from_bytes(size_bytes, "big")
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                data = fh.read(5)
                if len(data) < 5:
                    return None
                return (int.from_bytes(data[3:5], "big"),
                        int.from_bytes(data[1:3], "big"))
            fh.seek(seg_len - 2, 1)

    @staticmethod
    def _webp_size(head: bytes, fh) -> tuple[int, int] | None:
        chunk = head[12:16]
        if chunk == b"VP8X":
            fh.seek(24)
            data = fh.read(6)
            if len(data) < 6:
                return None
            return (int.from_bytes(data[0:3], "little") + 1,
                    int.from_bytes(data[3:6], "little") + 1)
        if chunk == b"VP8 ":
            fh.seek(23)
            data = fh.read(7)
            if len(data) < 7 or data[0:3] != b"\x9d\x01\x2a":
                return None
            return (int.from_bytes(data[3:5], "little") & 0x3FFF,
                    int.from_bytes(data[5:7], "little") & 0x3FFF)
        if chunk == b"VP8L":
            fh.seek(21)
            data = fh.read(4)
            if len(data) < 4 or data[0] != 0x2F:
                return None
            bits = int.from_bytes(data[1:4], "little")
            return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
        return None

    def _series_covers(self, series: Path) -> dict[str, str]:
        """Обложки серии по формату картинки: wide (16:9), vertical (9:16), any (≈квадрат).
        Имена файлов не важны — ориентация определяется по размерам.
        """
        best: dict[str, tuple[int, str]] = {}
        try:
            entries = sorted(series.iterdir())
        except OSError:
            return {}
        for p in entries:
            if not p.is_file() or p.name.startswith(".") or p.suffix.lower() not in IMAGE_EXTS:
                continue
            size = self._image_size(p)
            if not size:
                logger.warning("Обложка не распознана, пропускаю: %s", p)
                continue
            w, h = size
            if w <= 0 or h <= 0:
                continue
            ratio = w / h
            kind = "vertical" if ratio < 0.9 else ("wide" if ratio > 1.1 else "any")
            px = w * h
            cur = best.get(kind)
            if cur is None or px > cur[0]:
                best[kind] = (px, str(p.resolve()))
        out = {k: v[1] for k, v in best.items()}
        if "any" in out:
            out.setdefault("wide", out["any"])
            out.setdefault("vertical", out["any"])
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

    def _trim_size_cache(self, max_items: int = 10000) -> None:
        """P2.5: мягкое вытеснение (FIFO eviction) вместо полной очистки словаря."""
        if len(self._size_cache) <= max_items:
            return
        drop = len(self._size_cache) - int(max_items * 0.8)
        for k in list(self._size_cache)[:drop]:
            self._size_cache.pop(k, None)

    def _is_stable(self, path: Path) -> bool:
        """R2: require size stable across two stats to reduce race with writers."""
        try:
            size = path.stat().st_size
        except OSError:
            return False
        key = str(path)
        prev = self._size_cache.get(key)
        # скан, в котором файл встретился дважды (перекрывающиеся корни), не должен
        # считаться двумя подтверждениями устойчивости
        if prev and prev[0] == size and prev[2] != self._scan_seq:
            cycles = prev[1] + 1
            self._size_cache[key] = (size, cycles, self._scan_seq)
            self._trim_size_cache()
            return cycles >= self.cfg.file_stability_cycles
        if not prev or prev[0] != size:
            self._size_cache[key] = (size, 1, self._scan_seq)
        self._trim_size_cache()
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
                WHERE instr(shorts.folder_path, lv.folder_path || '/') = 1
                  AND instr(substr(shorts.folder_path, length(lv.folder_path) + 1), '/shorts/') > 0
                ORDER BY length(lv.folder_path) DESC
                LIMIT 1
            )
            WHERE parent_video_id IS NULL
              AND source = 'videomaker'
              AND EXISTS (
                SELECT 1 FROM long_videos lv
                WHERE instr(shorts.folder_path, lv.folder_path || '/') = 1
                  AND instr(substr(shorts.folder_path, length(lv.folder_path) + 1), '/shorts/') > 0
              )
            """
        )
        after = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM shorts WHERE parent_video_id IS NULL")
        return max(0, (before or {}).get("c", 0) - (after or {}).get("c", 0))

    def scan(self) -> dict[str, int]:
        self._scan_seq += 1
        stats = {"long": 0, "shorts": 0, "standalone": 0, "standalone_found": 0,
                 "checked": 0, "unstable": 0}
        max_depth = getattr(self.cfg, "watch_max_depth", 5)
        for spec in self.effective_root_specs():
            root = Path(spec["path"])
            mode = spec.get("kind", "auto")
            if not root.exists():
                continue
            if root.name.lower().startswith("shortsmaker") or (root / ".shortsmaker").exists():
                if mode != "series":
                    n, found_n = self._scan_standalone_root(root)
                    stats["standalone"] += n
                    stats["standalone_found"] += found_n
                continue
            self._walk(root, 0, max_depth, stats, mode)
            if mode != "series":
                self._renumber_standalone(root)
        linked = self._link_orphan_shorts()
        if linked:
            logger.info("Linked orphan shorts to series: %s", linked)
        filled = self._backfill_descriptions()
        if filled:
            logger.info("Backfilled descriptions: %s", filled)
        return stats

    def _renumber_standalone(self, root: Path) -> int:
        """Нумерация отдельнных шортсов = естественный порядок путей внутри корня.

        Иначе порядок в плане зависел от порядка обхода папки (ш1, ш10, ш2…) и от
        времени регистрации. Пересчитывается на каждом скане, поэтому стабильна.
        """
        root_s = str(root.resolve())
        rows = self.db.fetchall(
            "SELECT id, folder_path, order_index FROM shorts"
            " WHERE source='shortsmaker' AND parent_video_id IS NULL")
        mine = [r for r in rows if str(r["folder_path"]) == root_s
                or str(r["folder_path"]).startswith(root_s + os.sep)]
        mine.sort(key=lambda r: natural_key(str(r["folder_path"])[len(root_s):]))
        changed = 0
        for i, r in enumerate(mine):
            if r["order_index"] != i:
                self.db.execute("UPDATE shorts SET order_index=? WHERE id=?", (i, r["id"]))
                changed += 1
        if changed:
            logger.info("Renumbered standalone shorts under %s: %s", root_s, changed)
        return changed

    def _backfill_descriptions(self) -> int:
        """Дозаполняет пустые описания из файлов *_description.txt рядом с видео."""
        n = 0
        rows = self.db.fetchall(
            "SELECT id, video_path FROM shorts "
            "WHERE (description_text IS NULL OR description_text='') AND video_path IS NOT NULL")
        for r in rows:
            vp = Path(r["video_path"])
            stem = re.sub(r"_final$", "", vp.stem)
            text = (self._read_text(vp.with_name(stem + "_description.txt"))
                    or self._read_text(vp.with_name(vp.stem + "_description.txt"))
                    or self._read_text(vp.parent / f"{vp.parent.name}_description.txt"))
            if text:
                self.db.execute("UPDATE shorts SET description_text=? WHERE id=?",
                                (text, r["id"]))
                n += 1
        rows = self.db.fetchall(
            "SELECT id, folder_path FROM long_videos "
            "WHERE (description_text IS NULL OR description_text='') AND folder_path IS NOT NULL")
        for r in rows:
            folder = Path(r["folder_path"])
            text = self._series_text(folder, "description")
            if text:
                self.db.execute("UPDATE long_videos SET description_text=? WHERE id=?",
                                (text, r["id"]))
                n += 1
        return n

    def _walk(self, d: Path, depth: int, max_depth: int, stats: dict[str, int],
              mode: str = "auto") -> None:
        # устойчивость: одна недоступная папка не должна ронять весь цикл
        try:
            self._walk_inner(d, depth, max_depth, stats, mode)
        except OSError:
            logger.warning("Папка недоступна, пропускаю: %s", d)

    def _walk_inner(self, d: Path, depth: int, max_depth: int, stats: dict[str, int],
                    mode: str = "auto") -> None:
        if depth > max_depth:
            return
        if self._is_episode(d):
            stats["checked"] = stats.get("checked", 0) + 1
            if mode != "shorts":
                stats["long"] += self._scan_long(d, stats)
                stats["shorts"] += self._scan_shorts(d)
            else:
                stats["standalone"] += self._scan_shorts(d, with_parent=False)
            return
        if mode != "series":
            res = self._register_shorts_maker_short(d)
            if res:
                stats["standalone_found"] = stats.get("standalone_found", 0) + 1
                if res == 2:
                    stats["standalone"] += 1
                return
            loose = self._register_loose_shorts(d)
            if loose:
                stats["standalone"] += loose
                stats["standalone_found"] = stats.get("standalone_found", 0) + loose
                return
        for child in sorted(d.iterdir(), key=lambda p: natural_key(p.name)):
            if not child.is_dir() or self._is_junk_dir(child.name):
                continue
            self._walk(child, depth + 1, max_depth, stats, mode)

    def _is_episode(self, d: Path) -> bool:
        if (d / "vertical").is_dir() or (d / "wide").is_dir():
            return True
        # пакеты платформ внутри папки серии (стандарт видео мейкера)
        if self._package_dirs(d):
            return True
        platforms = list(self.cfg.platforms.keys())
        return bool(self._platform_map(d, platforms))

    def _scan_long(self, series: Path, stats: dict | None = None) -> int:
        platforms = list(self.cfg.platforms.keys())
        packages = self._package_dirs(series)
        # пакеты без финального файла своего формата не публикуются — считаем для панели
        no_final = sum(1 for name, pkg in packages.items()
                       if self._final_mp4(pkg / self._variant(name)) is None)
        if no_final and stats is not None:
            stats["no_final"] = stats.get("no_final", 0) + no_final
        pmap = self._platform_map(series, platforms)
        wide = self._final_mp4(series / "wide")
        vert = self._final_mp4(series / "vertical")
        # общий wide/vertical — только из пакетов тех платформ, чей это формат:
        # вертикаль внутри youtube/ не берём никому
        for name, pkg in packages.items():
            variant = self._variant(name)
            if wide is None and variant == "wide":
                wide = self._final_mp4(pkg / "wide")
            if vert is None and variant == "vertical":
                vert = self._final_mp4(pkg / "vertical")
        if not wide and not vert and not pmap:
            return 0
        unstable = False
        for p in {wide, vert} | {Path(v) for v in pmap.values()}:
            if p is not None and not self._is_stable(p):
                unstable = True
        if unstable:
            if stats is not None:
                stats["unstable"] = stats.get("unstable", 0) + 1
            return 0

        folder = str(series.resolve())
        existing = self.db.fetchone(
            "SELECT id FROM long_videos WHERE folder_path = ?", (folder,)
        )
        if existing:
            return 0
        # обложки: формат определяем по размерам картинки, имя не важно;
        # длинное видео в 16:9 (YouTube) берёт горизонтальную обложку
        covers = self._series_covers(series)
        cover = covers.get("wide")

        title = self._clean_name(series.name)
        meta_kv = self._meta_kv(series / "info_metadata.txt")
        title_text = meta_kv.get("package_title") or self._read_text(
            series / "info_metadata.txt"
        )[:200]
        desc_text = self._series_text(series, "description")
        tags_text = (
            meta_kv.get("package_hashtags")
            or self._series_text(series, "hashtags")
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

    def _shorts_dirs(self, series: Path) -> list[tuple[str | None, Path]]:
        """Папки шортсов серии: пакеты платформ (<platform>/shorts) + старый общий series/shorts."""
        out: list[tuple[str | None, Path]] = []
        for name, pkg in self._package_dirs(series).items():
            d = pkg / "shorts"
            if d.is_dir():
                out.append((name, d))
        legacy = series / "shorts"
        if legacy.is_dir():
            out.append((None, legacy))
        return out

    def _scan_shorts(self, series: Path, with_parent: bool = True) -> int:
        parent = self.db.fetchone(
            "SELECT id FROM long_videos WHERE folder_path = ?",
            (str(series.resolve()),),
        ) if with_parent else None
        parent_id = parent["id"] if parent else None
        count = 0
        for platform, shorts_dir in self._shorts_dirs(series):
            count += self._scan_shorts_dir(shorts_dir, platform, parent_id)
        return count

    def _scan_shorts_dir(self, shorts_dir: Path, platform: str | None, parent_id) -> int:
        """Шортсы одной папки: platform=None — старый общий формат, иначе шортсы пакета платформы."""
        count = 0
        platforms = list(self.cfg.platforms.keys())
        entries = sorted(
            (d for d in shorts_dir.iterdir() if d.is_dir() and not self._is_junk_dir(d.name)),
            key=lambda d: natural_key(d.name),
        )
        for i, short_dir in enumerate(entries):
            pmap = self._platform_map(short_dir, platforms)
            generic = [f for f in self._mp4s(short_dir) if f.stem not in platforms]
            video = (self._final_mp4(short_dir)
                     or (generic[0] if generic
                         else (Path(next(iter(pmap.values()))) if pmap else None)))
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
            cover = self._first_cover(short_dir)
            # шортс из пакета платформы принадлежит только этой платформе
            file_map = {platform: str(video.resolve())} if platform else pmap
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
                    (json.dumps(file_map) if file_map else None), now,
                ),
            )
            count += 1
        return count

    def _register_shorts_maker_short(self, d: Path) -> int:
        """Папка одного шортса Shorts Maker: *_final.mp4 + мета-файлы рядом.

        Возврат: 0 — не папка шортса, 1 — папка шортса (уже в базе / ещё не стабильна),
        2 — добавлена новая запись.
        """
        files = self._mp4s(d)
        if not files:
            return 0
        final = next((p for p in files if "_final" in p.stem), None)
        if not final:
            return 0
        metas = [p for p in d.iterdir() if p.is_file()
                 and not p.name.startswith("._") and p.name.endswith(META_MARKERS)]
        if not metas:
            return 0
        folder = str(d.resolve())
        if self.db.fetchone("SELECT id FROM shorts WHERE folder_path = ?", (folder,)):
            return 1
        if not self._is_stable(final) or not self._is_fresh_enough(final):
            return 1
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
        cover = next((p for p in sorted(d.glob("*_final_cover.*"))
                      if not p.name.startswith("._")), None) or self._first_cover(d)
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
        return 2

    def _register_loose_shorts(self, d: Path) -> int:
        """Отдельные mp4 с мета-файлами рядом (stem совпадает с префиксом меты)."""
        if d.parent.name == "shorts":
            return 0  # <серия>/shorts/<short>/ — за него отвечает _scan_shorts_dir
        files = self._mp4s(d)
        if not files:
            return 0
        metas = [p.name for p in d.iterdir() if p.is_file()
                 and not p.name.startswith("._") and p.name.endswith(META_MARKERS)]
        if not metas:
            return 0
        count = 0
        for video in files:
            stem = video.stem
            mine = [m for m in metas if m.startswith(stem + "_")]
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
            cover = next((p for p in sorted(d.glob(f"{stem}*cover*"))
                          if not p.name.startswith("._")), None)
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

    def _scan_standalone_root(self, root: Path) -> tuple[int, int]:
        """Корень ShortsMaker: папка = один клип (`*_final.mp4` + мета), либо одиночный mp4.

        Возврат: (новых, найдено). master_/preview_ одного клипа отдельно не публикуем.
        """
        new = found = 0
        handled: set[str] = set()
        for d in sorted((x for x in root.rglob("*") if x.is_dir()),
                        key=lambda x: natural_key(str(x.relative_to(root)))):
            if any(self._is_junk_dir(part) for part in d.relative_to(root).parts):
                continue  # мусорные папки внутри корня не обходим
            res = self._register_shorts_maker_short(d)
            if not res:
                continue
            found += 1
            handled.add(str(d.resolve()))
            if res == 2:
                new += 1
        by_dir: dict[str, list[Path]] = {}
        for video in root.rglob("*.mp4"):
            if video.name.startswith("._"):
                continue
            parts = video.relative_to(root).parts[:-1]
            if any(self._is_junk_dir(part) for part in parts):
                continue
            if str(video.parent.resolve()) in handled:
                continue  # папка уже зарегистрирована вместе с мета-файлами
            by_dir.setdefault(str(video.parent), []).append(video)
        loose: list[Path] = []
        for files in by_dir.values():
            finals = [f for f in files if "_final" in f.stem]
            if finals:
                loose.extend(finals)  # из папки берём только финальный файл
                continue
            # без _final: master_/preview_ одного клипа отдельными постами не публикуем
            loose.extend(f for f in files
                         if not f.stem.lower().startswith(("master", "preview"))
                         and not f.stem.lower().endswith(("_master", "_preview")))
        loose.sort(key=lambda p: natural_key(str(p.relative_to(root))))
        for order_index, video in enumerate(loose):
            key = f"{video.parent.resolve()}::{video.name}"
            if self.db.fetchone("SELECT id FROM shorts WHERE folder_path = ?", (key,)):
                found += 1
                continue
            if not self._is_stable(video) or not self._is_fresh_enough(video):
                found += 1
                continue
            found += 1
            now = self.clock.now().isoformat()
            title = self._clean_name(re.sub(r"_final$", "", video.stem))
            self.db.execute(
                """
                INSERT INTO shorts
                    (source, parent_video_id, folder_path, order_index,
                     video_path, title_text, description_text, hashtags_text, created_at)
                VALUES ('shortsmaker', NULL, ?, ?, ?, ?, '', '', ?)
                """,
                (key, order_index, str(video), title, now),
            )
            new += 1
            logger.info("Registered standalone short: %s", video)
        return new, found
