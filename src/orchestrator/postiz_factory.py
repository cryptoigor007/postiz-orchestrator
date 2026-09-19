from __future__ import annotations

import logging
import os

from .postiz import MockPostizClient, PostizClient

logger = logging.getLogger(__name__)


def create_postiz_client(dry_run: bool = False) -> PostizClient:
    """Factory: real HTTP client if token present and not dry_run, else mock."""
    token = os.getenv("POSTIZ_API_TOKEN", "").strip()
    if token and not dry_run:
        from .postiz_http import HttpPostizClient
        logger.info("Postiz: HttpPostizClient")
        return HttpPostizClient()
    logger.info("Postiz: MockPostizClient")
    return MockPostizClient()
