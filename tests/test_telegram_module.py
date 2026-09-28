"""Unit-тесты модуля Telegram (P3).

Injectable HTTP / dry-run; маппинг ошибок; лимит 50 МБ; registry.
"""

from __future__ import annotations

import json

import httpx
import pytest

from orchestrator.platforms import default_registry, load_modules, resolve_engine
from orchestrator.platforms.base import (
    ModuleError,
    ModuleErrorCode,
    NotSupported,
    PreparedMedia,
    PublishMeta,
)
from orchestrator.platforms.telegram.api import TelegramApi, _map_telegram_error
from orchestrator.platforms.telegram.module import (
    BOT_ID_PREFIX,
    TelegramModule,
    create_telegram_module,
)


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_manifest_loads():
    mod = create_telegram_module(token="t", chat_id="-1001", dry_run=True)
    assert mod.manifest.id == "telegram"
    assert mod.manifest.module_version == "1.0.0"
    assert mod.manifest.core_min == "8.5.0"
    caps = mod.capabilities()
    assert caps.get("publish") is True
    assert caps.get("early_upload") is False
    assert caps.get("schedule_publish") is False
    assert caps.get("update_metadata") is True
    assert caps.get("delete") is True


def test_auth_status_dry_run_ok():
    mod = create_telegram_module(token="tok", chat_id="-1001", dry_run=True)
    st = mod.auth_status()
    assert st.ok is True
    assert "dry_run" in (st.account or st.details or "")


def test_auth_status_no_token():
    mod = create_telegram_module(token="", chat_id="-1001", dry_run=True)
    st = mod.auth_status()
    assert st.ok is False


def test_publish_link_dry_run():
    mod = create_telegram_module(token="tok", chat_id="-100388", dry_run=True)
    meta = PublishMeta(
        title="Заголовок",
        description="Описание ролика",
        extra={"link": "https://youtu.be/abc123"},
    )
    media = PreparedMedia(path="", kind="text")
    res = mod.publish(media, meta)
    assert res.external_id.startswith(BOT_ID_PREFIX)
    assert res.state == "published"
    assert "t.me/" in res.url or res.url == ""  # dry_run channel username


def test_update_and_delete_dry_run():
    mod = create_telegram_module(token="tok", chat_id="-1001", dry_run=True)
    meta = PublishMeta(title="T", extra={"link": "https://youtu.be/x"})
    res = mod.publish(PreparedMedia(path="", kind="text"), meta)
    assert mod.update_metadata(res.external_id, PublishMeta(title="T2", extra={"link": "https://youtu.be/y"}))
    assert mod.delete(res.external_id) is True


def test_not_supported_upload_schedule():
    mod = create_telegram_module(token="t", chat_id="1", dry_run=True)
    with pytest.raises(NotSupported):
        mod.upload(PreparedMedia(path="", kind="video"), PublishMeta())
    with pytest.raises(NotSupported):
        mod.schedule_publish("tg:1", __import__("datetime").datetime.now())


def test_video_size_limit(tmp_path):
    big = tmp_path / "big.mp4"
    # 51 МБ фейк
    big.write_bytes(b"\x00" * (51 * 1024 * 1024))
    api = TelegramApi("tok", "-1001", dry_run=False, max_video_mb=50)
    with pytest.raises(ModuleError) as ei:
        api.send_video(big)
    assert ei.value.code == ModuleErrorCode.MEDIA_INVALID
    assert "50" in ei.value.message


def test_map_errors():
    e = _map_telegram_error(401, "Unauthorized", "sendMessage")
    assert e.code == ModuleErrorCode.AUTH_REQUIRED
    e = _map_telegram_error(429, "Too Many Requests: retry after 12", "sendMessage")
    assert e.code == ModuleErrorCode.RATE_LIMIT
    assert e.retryable
    e = _map_telegram_error(400, "message is too long", "sendMessage")
    assert e.code == ModuleErrorCode.MEDIA_INVALID
    e = _map_telegram_error(400, "file too big", "sendVideo")
    assert e.code == ModuleErrorCode.MEDIA_INVALID
    e = _map_telegram_error(403, "bot was kicked from the channel", "sendMessage")
    assert e.code == ModuleErrorCode.PLATFORM_REJECTED
    e = _map_telegram_error(500, "Internal", "sendMessage")
    assert e.code == ModuleErrorCode.TRANSIENT


def test_send_message_via_mock_transport():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url), request.read()))
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 42,
                    "chat": {"id": -1001, "username": "testchannel"},
                },
            },
        )

    from orchestrator.http_client import ModuleHttpClient

    http = ModuleHttpClient(
        platform="telegram",
        module_version="1.0.0",
        transport=_mock_transport(handler),
        max_retries=1,
    )
    api = TelegramApi("SECRET_TOKEN", "-1001", http=http, dry_run=False)
    res = api.send_message(
        "<b>Hi</b>",
        reply_markup={"inline_keyboard": [[{"text": "Go", "url": "https://youtu.be/x"}]]},
        link_preview_url="https://youtu.be/x",
    )
    assert res["message_id"] == 42
    assert len(calls) == 1
    method, url, body = calls[0]
    assert method == "POST"
    assert "SECRET_TOKEN" in url  # token in path — ok for Bot API; logs mask elsewhere
    payload = json.loads(body)
    assert payload["chat_id"] == "-1001"
    assert payload["parse_mode"] == "HTML"
    assert payload["link_preview_options"]["show_above_text"] is True
    assert payload["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://youtu.be/x"


def test_http_error_mapping_via_mock():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"ok": False, "description": "Forbidden: bot was blocked by the user"},
        )

    from orchestrator.http_client import ModuleHttpClient

    http = ModuleHttpClient(
        platform="telegram", transport=_mock_transport(handler), max_retries=1
    )
    api = TelegramApi("tok", "1", http=http)
    with pytest.raises(ModuleError) as ei:
        api.send_message("x")
    assert ei.value.code == ModuleErrorCode.PLATFORM_REJECTED


def test_registry_has_telegram():
    reg = default_registry()
    assert reg.has("telegram")
    mod = reg.create("telegram", token="t", chat_id="1", dry_run=True)
    assert isinstance(mod, TelegramModule)


def test_load_modules_telegram():
    engines = {"telegram": "module:telegram", "youtube": "postiz"}
    mods = load_modules(engines, deps={"token": "t", "chat_id": "-1", "dry_run": True})
    assert "telegram" in mods
    assert "youtube" not in mods  # postiz — не module


def test_resolve_engine_module():
    r = resolve_engine("module:telegram")
    assert r.kind == "module"
    assert r.module_id == "telegram"


def test_check_claims_unsupported():
    mod = create_telegram_module(token="t", chat_id="1", dry_run=True)
    cr = mod.check_claims("tg:1")
    assert cr.supported is False


def test_get_status():
    mod = create_telegram_module(token="t", chat_id="1", dry_run=True)
    st = mod.get_status("tg:99")
    assert st.state == "published"


def test_validate_config():
    mod = create_telegram_module(token="", chat_id="", dry_run=True)
    errs = mod.validate_config({})
    assert any("TOKEN" in e or "token" in e.lower() for e in errs)
