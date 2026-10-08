from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
from pathlib import Path

from .config import AppConfig
from dataclasses import dataclass

@dataclass
class MediaRef:
    id: str = ""
    path: str = ""

_SIZE_CACHE: dict[str, tuple[float, int]] = {}
_SIZE_CACHE_MAX = 4096

def _cached_size(path: str) -> int:
    """R7: bounded size cache to avoid repeated stat on large trees."""
    try:
        st = os.stat(path)
    except OSError:
        return 0
    mtime = st.st_mtime
    size = st.st_size
    cached = _SIZE_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    if len(_SIZE_CACHE) >= _SIZE_CACHE_MAX:
        # drop arbitrary oldest-ish quarter
        for i, k in enumerate(list(_SIZE_CACHE.keys())):
            if i >= _SIZE_CACHE_MAX // 4:
                break
            _SIZE_CACHE.pop(k, None)
    _SIZE_CACHE[path] = (mtime, size)
    return size


logger = logging.getLogger(__name__)


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def maybe_compress(path: str, platform: str, cfg: AppConfig) -> str:
    """Telegram (Bot API) принимает <=50 МБ — при необходимости сжимаем в кэш."""
    media_cfg = getattr(cfg, "media", None)
    if not media_cfg or platform != "telegram":
        return path
    limit_mb = int(getattr(media_cfg, "telegram_max_mb", 0))
    if limit_mb <= 0:
        return path
    limit = limit_mb * 1024 * 1024
    try:
        size = _cached_size(path)
    except OSError:
        return path
    if size <= limit:
        return path
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        logger.warning("ffmpeg не найден: файл %s больше лимита Telegram (%s МБ)", path, limit_mb)
        raise RuntimeError(
            f"telegram media exceeds {limit_mb}MB and ffmpeg unavailable: {path}"
        )
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0
    key = hashlib.sha1(f"{path}:{size}:{mtime}".encode()).hexdigest()[:16]
    cache_dir = Path(getattr(media_cfg, "cache_dir", "/mnt/video/.orch_cache")) / "telegram"
    cache_dir.mkdir(parents=True, exist_ok=True)
    dst = cache_dir / f"{key}.mp4"
    if dst.exists() and dst.stat().st_size <= limit:
        return str(dst)
    attempts = ((21, "10M"), (25, "5M"), (29, "2.5M"))
    for crf, maxrate in attempts:
        cmd = [
            ffmpeg, "-y", "-nostdin", "-loglevel", "error",
            "-i", path,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-maxrate", maxrate, "-bufsize", "8M",
            "-vf", "scale=w='if(gt(iw,ih),1920,-2)':h='if(gt(iw,ih),-2,1920)'",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(dst),
        ]
        try:
            subprocess.run(cmd, check=True, timeout=3600,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            logger.exception("ffmpeg сжатие не удалось: %s", path)
            # C7: do not return original oversized path
            continue
        if dst.exists() and dst.stat().st_size <= limit:
            logger.info("Сжат для Telegram: %s -> %s (%.1f МБ)", path, dst,
                        dst.stat().st_size / 1048576)
            return str(dst)
    # C7: never return a path still above telegram_max_mb
    if dst.exists() and dst.stat().st_size <= limit:
        return str(dst)
    raise RuntimeError(
        f"telegram media still exceeds {limit_mb}MB after compress: {path}"
    )


def make_media(
    path: str,
    platform: str,
    cfg: AppConfig,
    client=None,
    broker=None,
) -> MediaRef:
    """MediaRef for module path: symlink via broker, or local path ref for upload.

    ``client`` is ignored (legacy signature); platform upload_media removed.
    """
    path = maybe_compress(path, platform, cfg)
    media_cfg = getattr(cfg, "media", None)
    if (media_cfg is not None and getattr(media_cfg, "symlink_mode", False)
            and broker is not None and path.startswith(getattr(media_cfg, "local_prefix", "/mnt/video/"))):
        try:
            data = broker.symlink(path)
            if data and data.get("path"):
                return MediaRef(id=str(data.get("media_id") or "local"),
                                path=str(data["path"]))
        except Exception:
            logger.warning("symlink media failed, fallback to local ref", exc_info=True)
    # Module path: modules upload from local path / media_host (B2).
    return MediaRef(id="", path=path)


def prepublish_validate(
    path: str,
    platform: str,
    cfg: AppConfig,
    *,
    content_kind: str = "video_native",
) -> list[str]:
    """Pre-publish checks (size/mime/kind). Returns list of human-readable problems (empty = ok)."""
    problems: list[str] = []
    p = Path(path) if path else None
    if content_kind in ("video_native", "video_link") and p is not None and path:
        if not p.is_file():
            problems.append(f"media missing: {path}")
            return problems
        size_mb = p.stat().st_size / (1024 * 1024)
        media_cfg = getattr(cfg, "media", None)
        if platform == "telegram":
            limit = float(getattr(media_cfg, "telegram_max_mb", 50) or 50)
            if size_mb > limit:
                problems.append(
                    f"telegram size {size_mb:.1f}MB > {limit}MB — compress or use link-mode"
                )
        if platform == "x" and size_mb > 5 and content_kind != "promo_text":
            problems.append(f"x image/video size {size_mb:.1f}MB may exceed free-tier media limit")
    if content_kind == "promo_text" and platform in ("youtube",):
        problems.append("youtube does not accept promo_text content_kind as native upload")
    return problems
