from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
from pathlib import Path

from .config import AppConfig
from .postiz import MediaRef

logger = logging.getLogger(__name__)


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def maybe_compress(path: str, platform: str, cfg: AppConfig) -> str:
    """Telegram (Bot API) принимает <=50 МБ — при необходимости сжимаем в кэш."""
    media_cfg = getattr(cfg, "media", None)
    if not media_cfg or platform != "telegram":
        return path
    limit = int(getattr(media_cfg, "telegram_max_mb", 49)) * 1024 * 1024
    try:
        size = os.path.getsize(path)
    except OSError:
        return path
    if size <= limit:
        return path
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        logger.warning("ffmpeg не найден: файл %s больше лимита Telegram", path)
        return path
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
    attempts = ((26, "4M"), (30, "2.5M"), (34, "1.5M"))
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
            return path
        if dst.exists() and dst.stat().st_size <= limit:
            logger.info("Сжат для Telegram: %s -> %s (%.1f МБ)", path, dst,
                        dst.stat().st_size / 1048576)
            return str(dst)
    if dst.exists() and dst.stat().st_size < size:
        return str(dst)
    return path


def make_media(path: str, platform: str, cfg: AppConfig, postiz, broker=None) -> MediaRef:
    """MediaRef без копирования: симлинк на файл сервера; иначе — обычная загрузка."""
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
            logger.warning("symlink media failed, fallback to upload", exc_info=True)
    return postiz.upload_media(path, platform)
