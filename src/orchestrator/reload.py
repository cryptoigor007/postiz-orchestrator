from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

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


def apply_config_to_comps(comps: dict[str, Any], new_cfg: AppConfig) -> list[str]:
    """Push new_cfg into live components that hold a cfg reference (L38).

    Returns list of component keys updated. Some services (http server bind, etc.)
    still require process restart — those are listed in the log message.
    """
    updated: list[str] = []
    comps["cfg"] = new_cfg
    updated.append("cfg")
    for key, obj in list(comps.items()):
        if key == "cfg":
            continue
        if obj is not None and hasattr(obj, "cfg"):
            try:
                obj.cfg = new_cfg
                updated.append(key)
            except Exception:
                logger.exception("failed to update cfg on %s", key)
    logger.info(
        "Config applied to comps=%s; restart required for HTTP bind/TLS/broker env",
        updated,
    )
    return updated
