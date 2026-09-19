from __future__ import annotations

import json
import logging
import re
from typing import Any

from .config import AppConfig
from .db import Database

logger = logging.getLogger(__name__)

SCHEDULE_SETTINGS_KEY = "schedule_settings"
GROUPS_KEY = "network_groups"

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
KIND_TO_CFG = {
    "long": "long_video",
    "thematic": "shorts_thematic",
    "standalone": "shorts_standalone",
}
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _load_json(db: Database, key: str, default: Any) -> Any:
    raw = db.get_setting(key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        logger.warning("invalid %s setting", key)
        return default


def load_groups(db: Database) -> list[dict[str, Any]]:
    data = _load_json(db, GROUPS_KEY, [])
    out: list[dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            platforms = [str(p).strip() for p in (item.get("platforms") or [])]
            platforms = [p for p in platforms if p]
            if name and platforms:
                out.append({"name": name, "platforms": platforms})
    return out


def save_groups(db: Database, groups: list[dict[str, Any]]) -> None:
    db.set_setting(GROUPS_KEY, json.dumps(groups, ensure_ascii=False))


def load_schedule_settings(db: Database) -> dict[str, Any]:
    data = _load_json(db, SCHEDULE_SETTINGS_KEY, {})
    return data if isinstance(data, dict) else {}


def save_schedule_settings(db: Database, settings: dict[str, Any]) -> None:
    db.set_setting(SCHEDULE_SETTINGS_KEY, json.dumps(settings, ensure_ascii=False))


def group_for(platform: str, groups: list[dict[str, Any]]) -> dict[str, Any] | None:
    for g in groups:
        if platform in g.get("platforms", []):
            return g
    return None


def _override_for(db: Database, platform: str, kind: str) -> dict[str, Any] | None:
    settings = load_schedule_settings(db)
    groups = load_groups(db)
    g = group_for(platform, groups)
    if g:
        block = settings.get(f"group:{g['name']}")
        if isinstance(block, dict) and isinstance(block.get(kind), dict):
            return block[kind]
    block = settings.get(platform)
    if isinstance(block, dict) and isinstance(block.get(kind), dict):
        return block[kind]
    return None


def effective(db: Database, cfg: AppConfig, platform: str, kind: str) -> dict[str, Any]:
    """Итоговые настройки слота для платформы и типа контента.

    Порядок: override группы (если платформа в группе с настройками) → override платформы
    → конфиг → дефолты. Ключи результата нормализованы по типу:
    long: days/time; thematic: time; standalone: days/times.
    """
    if kind not in KIND_TO_CFG:
        raise ValueError(f"unknown kind: {kind}")
    base = dict(cfg.schedules.get(KIND_TO_CFG[kind], {}) or {})
    over = _override_for(db, platform, kind) or {}

    if kind == "thematic":
        return {"time": str(over.get("time") or base.get("default_time") or "20:30")}

    if kind == "long":
        days = over.get("days") or base.get("days") or ["tue", "fri"]
        time_str = over.get("time") or base.get("time") or "16:00"
        return {
            "days": [str(d) for d in days],
            "time": str(time_str),
            "exception_days": list(base.get("exception_days", [])),
        }

    days = over.get("days") if over.get("days") is not None else base.get("days", [])
    times = over.get("times") or base.get("times") or []
    return {
        "days": [str(d) for d in (days or [])],
        "times": [str(t) for t in times],
    }


def effective_daily_limit(db: Database, cfg: AppConfig, platform: str) -> int:
    settings = load_schedule_settings(db)
    block = settings.get(platform)
    if isinstance(block, dict):
        val = block.get("daily_limit")
        if isinstance(val, int) and 0 <= val <= 50:
            return val
    pcfg = cfg.platforms.get(platform)
    return int(getattr(pcfg, "daily_limit", 0) or 0)


def validate_time(value: Any) -> bool:
    return bool(TIME_RE.match(str(value or "")))


def validate_schedule_settings(settings: Any) -> tuple[bool, str]:
    if not isinstance(settings, dict):
        return False, "schedule_settings must be an object"
    for key, block in settings.items():
        if not isinstance(block, dict):
            return False, f"{key}: must be an object"
        for kind in ("long", "thematic", "standalone"):
            part = block.get(kind)
            if part is None:
                continue
            if not isinstance(part, dict):
                return False, f"{key}.{kind}: must be an object"
            if kind == "long":
                if "days" in part and (
                    not isinstance(part["days"], list)
                    or any(str(d).lower()[:3] not in DAYS for d in part["days"])
                ):
                    return False, f"{key}.long.days: invalid"
                if "time" in part and not validate_time(part["time"]):
                    return False, f"{key}.long.time: invalid"
            elif kind == "thematic":
                if "time" in part and not validate_time(part["time"]):
                    return False, f"{key}.thematic.time: invalid"
            else:
                if "days" in part and (
                    not isinstance(part["days"], list)
                    or any(str(d).lower()[:3] not in DAYS for d in part["days"])
                ):
                    return False, f"{key}.standalone.days: invalid"
                if "times" in part and (
                    not isinstance(part["times"], list)
                    or any(not validate_time(t) for t in part["times"])
                ):
                    return False, f"{key}.standalone.times: invalid"
        if "daily_limit" in block:
            val = block["daily_limit"]
            if not isinstance(val, int) or not (0 <= val <= 50):
                return False, f"{key}.daily_limit: invalid"
    return True, ""


def validate_groups(groups: Any, known_platforms: list[str]) -> tuple[bool, str]:
    if not isinstance(groups, list):
        return False, "groups must be a list"
    seen = set()
    for g in groups:
        if not isinstance(g, dict):
            return False, "group must be an object"
        name = str(g.get("name") or "").strip()
        if not name:
            return False, "group.name is required"
        if name in seen:
            return False, f"duplicate group name: {name}"
        seen.add(name)
        plats = g.get("platforms")
        if not isinstance(plats, list) or not plats:
            return False, f"group {name}: platforms required"
        for p in plats:
            if p not in known_platforms:
                return False, f"group {name}: unknown platform {p}"
    return True, ""


SCHEDULING_MODE_KEY = "scheduling_mode"


def scheduling_mode(db: Database) -> str:
    """auto — раскладывать без подтверждения; manual — ждать кнопку/дату в панели."""
    raw = db.get_setting(SCHEDULING_MODE_KEY)
    return "auto" if str(raw or "").strip().lower() == "auto" else "manual"


def set_scheduling_mode(db: Database, mode: str) -> None:
    db.set_setting(SCHEDULING_MODE_KEY, "auto" if mode == "auto" else "manual")
