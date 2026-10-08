from __future__ import annotations

import logging
from typing import Any

from .engines.token_broker_client import TokenBrokerClient

logger = logging.getLogger(__name__)


def build_manual_sources(cfg: Any, env: dict) -> dict[str, Any]:
    """Build manual-source objects from native provider modules only.

    Legacy legacy transport transports are intentionally not resolvable in the
    production runtime. Manual adoption is a metadata/storage operation; actual
    platform transport remains inside the native module registry.
    """
    broker = None
    if env.get("TOKEN_BROKER_URL"):
        broker = TokenBrokerClient(env["TOKEN_BROKER_URL"], env.get("TOKEN_BROKER_SECRET", ""))

    out: dict[str, Any] = {}
    for platform, pcfg in (cfg.platforms or {}).items():
        if not getattr(pcfg, "enabled", True):
            continue
        try:
            engine = str(cfg.engine_for(platform) or "").strip().lower()
            if not engine.startswith("module:"):
                logger.warning("manual_sources: skipping non-module engine for %s", platform)
                continue
            module_id = engine.split(":", 1)[1].strip()
            from .platforms import default_registry
            reg = default_registry()
            if not reg.has(module_id):
                logger.error("manual_sources: module %r not registered (platform=%s)", module_id, platform)
                continue
            aid = str(getattr(pcfg, "account_id", "") or getattr(pcfg, "integration_id", "") or "")

            def _token_provider(p: str = platform, b: Any = broker, i: str = aid) -> str:
                if b is not None:
                    try:
                        value = str((b.get(p, i) or {}).get("token") or "")
                        if value:
                            return value
                    except Exception:
                        logger.debug("manual token broker lookup failed", exc_info=True)
                try:
                    from .auth_tokens import get_access_token
                    return get_access_token(p, account_id=i)
                except Exception:
                    return ""

            out[platform] = reg.create(
                module_id, token_provider=_token_provider, cfg=cfg, dry_run=False,
                http=None, account_id=aid,
            )
        except Exception:
            logger.exception("manual_sources: failed to create module for %s", platform)
    return out
