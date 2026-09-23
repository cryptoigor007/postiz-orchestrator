from __future__ import annotations

import logging
import os

from .postiz import MockPostizClient, PostizClient

logger = logging.getLogger(__name__)


def create_postiz_client(dry_run: bool = False) -> PostizClient:
    """Factory: real HTTP client unless dry_run.

    P1-8: при `dry_run=False` и пустом `POSTIZ_API_TOKEN` — fail-fast. Раньше молча
    возвращался MockPostizClient: панель показывала «запланировано», реальной
    публикации не было, а после рестарта строки уходили в error.
    """
    token = os.getenv("POSTIZ_API_TOKEN", "").strip()
    if dry_run:
        logger.info("Postiz: MockPostizClient (dry-run)")
        return MockPostizClient()
    if not token:
        raise RuntimeError(
            "POSTIZ_API_TOKEN пуст, а режим не dry-run: отказываюсь подменять клиент моком "
            "(иначе публикации только имитируются). Задайте POSTIZ_API_TOKEN "
            "или запустите с --dry-run."
        )
    from .postiz_http import HttpPostizClient
    logger.info("Postiz: HttpPostizClient")
    return HttpPostizClient()
