from __future__ import annotations
from typing import Any

from .engines.browser_engine import BrowserEngine
from .engines.direct_youtube import YouTubeEngine
from .engines.n8n_engine import N8nEngine
from .engines.postiz_engine import PostizEngine
from .engines.token_broker_client import TokenBrokerClient


def build_manual_sources(cfg: Any, postiz: Any, env: dict) -> dict[str, Any]:
    """Map platform -> Destination engine based on config.engines."""
    broker = None
    if env.get("TOKEN_BROKER_URL"):
        broker = TokenBrokerClient(env["TOKEN_BROKER_URL"], env.get("TOKEN_BROKER_SECRET", ""))
    n8n_url = env.get("N8N_URL")

    out: dict[str, Any] = {}
    for platform in cfg.platforms:
        engine = cfg.engine_for(platform)
        if engine == "postiz":
            out[platform] = PostizEngine(postiz)
        elif engine == "direct" and platform == "youtube" and broker is not None:
            out[platform] = YouTubeEngine(
                token_provider=lambda p=platform, b=broker: b.get(p).get("token", "")
            )
        elif engine == "n8n" and n8n_url:
            out[platform] = N8nEngine(n8n_url, env.get("N8N_TOKEN", ""))
        elif engine == "browser":
            out[platform] = BrowserEngine()
    return out
