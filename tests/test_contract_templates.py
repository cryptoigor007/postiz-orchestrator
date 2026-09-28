"""Contract-шаблоны: skip без live-ключей. Готовы к [ВЛАДЕЛЕЦ].

Включить:
  ORCH_CONTRACT=1
  + TELEGRAM_BOT_TOKEN + TELEGRAM_PUBLISH_CHAT_ID
  + YOUTUBE token store / broker
  + POSTIZ_API_TOKEN + integration ids
"""

from __future__ import annotations

import os

import pytest

from orchestrator.platforms.base import PreparedMedia, PublishMeta

NEED = pytest.mark.skipif(
    os.getenv("ORCH_CONTRACT", "") not in ("1", "true", "yes"),
    reason="ORCH_CONTRACT не включён — live contract [ЖДЁТ] владельца",
)


@NEED
def test_contract_telegram_cycle():
    from orchestrator.platforms.telegram import create_telegram_module

    tok = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_PUBLISH_CHAT_ID"]
    mod = create_telegram_module(token=tok, chat_id=chat, dry_run=False)
    assert mod.auth_status().ok
    res = mod.publish(
        PreparedMedia(path="", kind="text"),
        PublishMeta(title="contract-test", description="auto", extra={"link": "https://youtu.be/dQw4w9WgXcQ"}),
    )
    assert res.external_id.startswith("tg:")
    assert mod.update_metadata(res.external_id, PublishMeta(title="contract-edited", extra={"link": "https://youtu.be/dQw4w9WgXcQ"}))
    assert mod.delete(res.external_id)


@NEED
def test_contract_youtube_auth_only():
    """Только auth_status — полная загрузка требует testPostiz + квоту."""
    from orchestrator.platforms.youtube import create_youtube_module

    mod = create_youtube_module(dry_run=False)
    st = mod.auth_status()
    assert st.ok, st.details


@NEED
def test_contract_postiz_list():
    # если клиент недоступен — skip
    pytest.importorskip("orchestrator.postiz_http")
