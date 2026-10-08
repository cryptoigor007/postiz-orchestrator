from __future__ import annotations

from copy import deepcopy
from typing import Any

CURRENT_CONFIG_SCHEMA_VERSION = 2


def migrate_config_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Upgrade persisted YAML config shapes without mutating caller input.

    v1 -> v2: account identity is canonical `account_id`; the legacy
    `integration_id` remains accepted by AppConfig for read compatibility,
    but is copied into account_id when account_id is absent.
    """
    data = deepcopy(dict(raw or {}))
    try:
        version = int(data.get("config_schema_version", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("config_schema_version must be an integer") from exc
    if version > CURRENT_CONFIG_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported config_schema_version={version}; current={CURRENT_CONFIG_SCHEMA_VERSION}"
        )
    if version < 2:
        platforms = data.get("platforms") or {}
        if isinstance(platforms, dict):
            for _, cfg in platforms.items():
                if isinstance(cfg, dict) and not cfg.get("account_id") and cfg.get("integration_id"):
                    cfg["account_id"] = cfg["integration_id"]
        data["config_schema_version"] = 2
        version = 2
    data["config_schema_version"] = version
    return data
