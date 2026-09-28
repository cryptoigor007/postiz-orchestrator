"""Доп. unit-тесты P2: HTTP-клиент (A5), schedule/update/publish, token store, errors."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.base import (
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    PublishMeta,
)
from orchestrator.platforms.youtube.module import YouTubeModule


def _resp(
    status: int,
    body: dict | str | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    content = b""
    if isinstance(body, dict):
        content = json.dumps(body).encode()
    elif isinstance(body, str):
        content = body.encode()
    return httpx.Response(
        status,
        content=content,
        headers=headers or {"content-type": "application/json"},
        request=httpx.Request("GET", "https://example.test"),
    )


class ScriptedTransport(httpx.BaseTransport):
    def __init__(self, script: list[httpx.Response]) -> None:
        self.script = list(script)
        self.calls: list[tuple[str, str]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, str(request.url)))
        if not self.script:
            return _resp(500, {"error": {"message": "no more scripted responses"}})
        return self.script.pop(0)


@pytest.fixture
def video_file(tmp_path: Path) -> Path:
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    return p


def test_http_client_retries_5xx() -> None:
    transport = ScriptedTransport(
        [
            _resp(503, {"error": "unavailable"}),
            _resp(200, {"ok": True}),
        ]
    )
    client = ModuleHttpClient(
        platform="youtube",
        module_version="2.1.1",
        transport=transport,
        max_retries=3,
    )
    import orchestrator.http_client as hc

    orig = hc.time.sleep
    hc.time.sleep = lambda s: None  # type: ignore
    try:
        resp = client.request("GET", "https://example.test/x", idempotent=True)
    finally:
        hc.time.sleep = orig
    assert resp.status_code == 200
    assert len(transport.calls) == 2


def test_http_client_respects_retry_after() -> None:
    transport = ScriptedTransport(
        [
            _resp(429, {"error": "rate"}, headers={"Retry-After": "1"}),
            _resp(200, {"ok": True}),
        ]
    )
    client = ModuleHttpClient(
        platform="youtube",
        module_version="2.1.1",
        transport=transport,
        max_retries=3,
    )
    import orchestrator.http_client as hc

    slept: list[float] = []
    orig = hc.time.sleep
    hc.time.sleep = lambda s: slept.append(s)  # type: ignore
    try:
        resp = client.request("GET", "https://example.test/r", idempotent=True)
    finally:
        hc.time.sleep = orig
    assert resp.status_code == 200
    assert slept and slept[0] >= 1.0


def test_http_client_no_retry_post_5xx() -> None:
    transport = ScriptedTransport([_resp(503, {"error": "fail"})])
    client = ModuleHttpClient(
        platform="youtube",
        module_version="2.1.1",
        transport=transport,
        max_retries=3,
    )
    resp = client.request(
        "POST", "https://example.test/create", idempotent=False, json={"a": 1}
    )
    assert resp.status_code == 503
    assert len(transport.calls) == 1


def test_module_schedule_publish(video_file: Path) -> None:
    transport = ScriptedTransport(
        [
            _resp(200, {"id": "vidSched", "status": {"privacyStatus": "private"}}),
        ]
    )
    http = ModuleHttpClient(platform="youtube", module_version="2.1.1", transport=transport)
    mod = YouTubeModule(lambda: "tok", http=http)
    when = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert mod.schedule_publish("vidSched", when) is True
    assert transport.calls and transport.calls[0][0] == "PUT"


def test_module_update_metadata() -> None:
    transport = ScriptedTransport(
        [
            _resp(200, {"id": "vidUp", "snippet": {"title": "New"}}),
        ]
    )
    http = ModuleHttpClient(platform="youtube", module_version="2.1.1", transport=transport)
    mod = YouTubeModule(lambda: "tok", http=http)
    ok = mod.update_metadata(
        "vidUp",
        PublishMeta(title="New Title", description="Desc", hashtags="#a #b"),
    )
    assert ok is True
    assert transport.calls[0][0] == "PUT"


def test_module_publish_public(video_file: Path) -> None:
    transport = ScriptedTransport(
        [
            _resp(200, {}, headers={"Location": "https://upload.example/session"}),
            _resp(200, {"id": "vidPub", "status": {"privacyStatus": "public"}}),
        ]
    )
    http = ModuleHttpClient(platform="youtube", module_version="2.1.1", transport=transport)
    mod = YouTubeModule(lambda: "tok", http=http)
    result = mod.publish(
        mod.prepare(MediaSpec(path=str(video_file))),
        PublishMeta(title="Pub Now"),
    )
    assert result.external_id == "vidPub"
    assert result.state == "published"
    assert "youtu.be" in result.url


def test_module_rate_limit_on_upload(video_file: Path) -> None:
    transport = ScriptedTransport(
        [
            _resp(
                403,
                {
                    "error": {
                        "message": "rateLimitExceeded",
                        "errors": [{"reason": "rateLimitExceeded"}],
                    }
                },
            ),
        ]
    )
    http = ModuleHttpClient(platform="youtube", module_version="2.1.1", transport=transport)
    mod = YouTubeModule(lambda: "tok", http=http)
    with pytest.raises(ModuleError) as ei:
        mod.upload(
            mod.prepare(MediaSpec(path=str(video_file))),
            PublishMeta(title="RL"),
        )
    assert ei.value.code == ModuleErrorCode.RATE_LIMIT
    assert ei.value.retryable


def test_token_store_load_save(tmp_path: Path) -> None:
    from orchestrator.platforms.youtube.token_store import TokenData, YouTubeTokenStore

    path = tmp_path / "youtube.json"
    store = YouTubeTokenStore(path, client_id="cid", client_secret="csec")
    store.save(
        TokenData(
            access_token="acc1",
            refresh_token="ref1",
            expires_at=9999999999.0,
        )
    )
    assert path.is_file()
    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "acc1"
    assert loaded.refresh_token == "ref1"
    assert store.get_access_token() == "acc1"


def test_token_store_refresh(tmp_path: Path) -> None:
    from orchestrator.platforms.youtube.token_store import TokenData, YouTubeTokenStore

    path = tmp_path / "youtube.json"
    transport = ScriptedTransport(
        [
            _resp(
                200,
                {
                    "access_token": "new_acc",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            ),
        ]
    )
    http = ModuleHttpClient(platform="youtube", module_version="2.1.1", transport=transport)
    store = YouTubeTokenStore(
        path, client_id="cid", client_secret="csec", http=http, skew_sec=0
    )
    store.save(
        TokenData(
            access_token="old",
            refresh_token="ref1",
            expires_at=1.0,
        )
    )
    tok = store.get_access_token()
    assert tok == "new_acc"
    reloaded = store.load()
    assert reloaded is not None
    assert reloaded.access_token == "new_acc"
    assert reloaded.refresh_token == "ref1"


def test_token_store_invalid_grant(tmp_path: Path) -> None:
    from orchestrator.platforms.youtube.token_store import TokenData, YouTubeTokenStore

    path = tmp_path / "youtube.json"
    transport = ScriptedTransport(
        [
            _resp(
                400,
                {
                    "error": "invalid_grant",
                    "error_description": "Token has been expired or revoked",
                },
            ),
        ]
    )
    http = ModuleHttpClient(platform="youtube", module_version="2.1.1", transport=transport)
    store = YouTubeTokenStore(
        path, client_id="cid", client_secret="csec", http=http, skew_sec=0
    )
    store.save(TokenData(access_token="old", refresh_token="bad", expires_at=1.0))
    with pytest.raises(ModuleError) as ei:
        store.get_access_token()
    assert ei.value.code == ModuleErrorCode.AUTH_REQUIRED


def test_errors_dict() -> None:
    from orchestrator.platforms.errors import ERROR_MESSAGES, message_for

    assert ModuleErrorCode.QUOTA in ERROR_MESSAGES
    msg, action = message_for(ModuleErrorCode.AUTH_REQUIRED)
    assert "авторизац" in msg.lower() or "переподключ" in action.lower()


def test_manifest_version_2_1() -> None:
    from orchestrator.platforms.manifest import load_manifest

    m = load_manifest(
        Path(__file__).resolve().parents[1]
        / "src"
        / "orchestrator"
        / "platforms"
        / "youtube"
        / "manifest.yaml"
    )
    assert m.module_version == "2.1.1"


# --- A7 debug bodies ---


def test_http_debug_body_written(tmp_path: Path) -> None:
    from orchestrator.http_client import ModuleHttpClient

    debug_dir = tmp_path / "http-debug"
    transport = ScriptedTransport(
        [_resp(403, {"error": {"message": "Bearer ya29.secretTOKEN and token=abc"}})]
    )
    client = ModuleHttpClient(
        platform="youtube",
        module_version="2.1.1",
        transport=transport,
        debug_bodies=True,
        debug_dir=debug_dir,
        max_retries=1,
    )
    resp = client.request("GET", "https://example.test/err", idempotent=True)
    assert resp.status_code == 403
    files = list(debug_dir.glob("*.txt"))
    assert files, "debug file should be written"
    content = files[0].read_text(encoding="utf-8")
    assert "***" in content or "secretTOKEN" not in content
    assert "ya29.secretTOKEN" not in content


def test_cleanup_debug_dir(tmp_path: Path) -> None:
    import time as _time

    from orchestrator.http_client import cleanup_debug_dir

    d = tmp_path / "dbg"
    d.mkdir()
    old = d / "old.txt"
    old.write_text("x")
    # backdate mtime
    old_ts = _time.time() - 8 * 24 * 3600
    os.utime(old, (old_ts, old_ts))
    new = d / "new.txt"
    new.write_text("y")
    removed = cleanup_debug_dir(d, retention_sec=7 * 24 * 3600)
    assert removed >= 1
    assert not old.exists()
    assert new.exists()


# --- clear_schedule / rejected ---


def test_module_clear_schedule() -> None:
    transport = ScriptedTransport(
        [_resp(200, {"id": "vidClr", "status": {"privacyStatus": "private"}})]
    )
    http = ModuleHttpClient(platform="youtube", module_version="2.1.1", transport=transport)
    mod = YouTubeModule(lambda: "tok", http=http)
    assert mod.clear_schedule("vidClr") is True
    assert transport.calls[0][0] == "PUT"


def test_resumable_rejected_status(video_file: Path) -> None:
    from orchestrator.platforms.youtube.api import YouTubeApi

    transport = ScriptedTransport(
        [
            _resp(200, {}, headers={"Location": "https://upload.example/s"}),
            _resp(
                200,
                {
                    "id": "vidRej",
                    "status": {"uploadStatus": "rejected", "rejectionReason": "copyright"},
                },
            ),
        ]
    )
    http = ModuleHttpClient(platform="youtube", module_version="2.1.1", transport=transport)
    api = YouTubeApi(lambda: "tok", http=http)
    with pytest.raises(ModuleError) as ei:
        api.resumable_upload(str(video_file), title="x")
    assert ei.value.code == ModuleErrorCode.PLATFORM_REJECTED


def test_resume_session_persists(tmp_path: Path, video_file: Path) -> None:
    from orchestrator.platforms.youtube.api import YouTubeApi

    # first call: init + 308 mid-way would need large file; simulate via session file
    session_dir = tmp_path / "resume"
    # minimal: init succeeds, one chunk final
    transport = ScriptedTransport(
        [
            _resp(200, {}, headers={"Location": "https://upload.example/sess1"}),
            _resp(200, {"id": "vidRes", "status": {"uploadStatus": "uploaded"}}),
        ]
    )
    http = ModuleHttpClient(platform="youtube", module_version="2.1.1", transport=transport)
    api = YouTubeApi(lambda: "tok", http=http)
    data = api.resumable_upload(
        str(video_file), title="resume-test", resume_dir=session_dir
    )
    assert data["id"] == "vidRes"
    # session should be cleaned after success
    left = list(session_dir.glob("yt_upload_*.json"))
    assert left == []
