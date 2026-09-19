from __future__ import annotations

from typing import Any

# platform engine -> capabilities
REGISTRY: dict[str, dict[str, bool]] = {
    "postiz": {"publish": True, "list": False, "update": False, "delete": False,
               "claims": False, "experimental": False},
    "direct": {"publish": True, "list": True, "update": True, "delete": True,
               "claims": True, "experimental": False},
    "n8n": {"publish": True, "list": True, "update": False, "delete": False,
            "claims": False, "experimental": False},
    "browser": {"publish": True, "list": True, "update": False, "delete": False,
                "claims": False, "experimental": True},
}


def capabilities(engine: str) -> dict[str, bool]:
    return REGISTRY.get(engine, {})


def select_engine(cfg: Any, platform: str) -> str:
    return cfg.engine_for(platform)
