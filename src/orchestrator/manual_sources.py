from __future__ import annotations

import logging
from typing import Any

from .engines.browser_engine import BrowserEngine
from .engines.direct_youtube import YouTubeEngine
from .engines.n8n_engine import N8nEngine
from .engines.postiz_engine import PostizEngine
from .engines.token_broker_client import TokenBrokerClient

logger = logging.getLogger(__name__)


def build_manual_sources(cfg: Any, postiz: Any, env: dict) -> dict[str, Any]:
    """Map platform -> Destination engine based on config.engines.

    Поддержка engines.<platform>:
      postiz | n8n | browser | direct (legacy YouTubeEngine)
      module:<id>  — PlatformModule из platforms registry (P2+, без авто-включения в прод).
    """
    broker = None
    if env.get("TOKEN_BROKER_URL"):
        broker = TokenBrokerClient(env["TOKEN_BROKER_URL"], env.get("TOKEN_BROKER_SECRET", ""))
    n8n_url = env.get("N8N_URL")

    out: dict[str, Any] = {}
    for platform, pcfg in cfg.platforms.items():
        if not getattr(pcfg, "enabled", True):
            continue
        engine = cfg.engine_for(platform)
        eng = str(engine or "").strip().lower()

        if eng.startswith("module:"):
            module_id = eng.split(":", 1)[1].strip()
            try:
                from .platforms import default_registry

                reg = default_registry()
                if not reg.has(module_id):
                    logger.error(
                        "manual_sources: module %r не зарегистрирован (platform=%s)",
                        module_id,
                        platform,
                    )
                    continue
                iid = getattr(pcfg, "integration_id", "") or ""

                def _token_provider(
                    p: str = platform, b: Any = broker, i: str = iid
                ) -> str:
                    if b is None:
                        return ""
                    try:
                        return str((b.get(p, i) or {}).get("token") or "")
                    except Exception:
                        return ""

                out[platform] = reg.create(
                    module_id,
                    token_provider=_token_provider,
                    cfg=cfg,
                    dry_run=False,
                    http=None,
                )
            except Exception:
                logger.exception(
                    "manual_sources: не удалось создать module:%s для %s",
                    module_id,
                    platform,
                )
            continue

        if eng == "postiz":
            out[platform] = PostizEngine(postiz)
        elif eng == "direct" and platform == "youtube" and broker is not None:
            # legacy direct path (до P5); alias direct→module:youtube — после P5
            iid = getattr(pcfg, "integration_id", "") or ""
            out[platform] = YouTubeEngine(
                token_provider=lambda p=platform, b=broker, i=iid: b.get(p, i).get("token", "")
            )
        elif eng == "n8n" and n8n_url:
            out[platform] = N8nEngine(n8n_url, env.get("N8N_TOKEN", ""))
        elif eng == "browser":
            out[platform] = BrowserEngine()
    return out
