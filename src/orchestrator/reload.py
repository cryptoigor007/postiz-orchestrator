from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .config import AppConfig, load_config

logger = logging.getLogger(__name__)


def reload_config(path: str | Path, current: AppConfig) -> tuple[AppConfig | None, str]:
    """Load and validate new config. On failure return (None, error) — caller keeps current."""
    path = Path(path)
    backup = path.with_suffix(path.suffix + ".bak")
    try:
        new_cfg = load_config(path)
    except Exception as e:
        logger.error("Config validation failed: %s", e)
        return None, str(e)
    try:
        if path.exists():
            shutil.copy2(path, backup)
    except Exception:
        pass
    logger.info("Config reloaded from %s", path)
    return new_cfg, "ok"
