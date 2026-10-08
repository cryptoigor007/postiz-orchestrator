"""X module unit tests (mock / dry-run)."""
from __future__ import annotations

import pytest

from orchestrator.platforms.base import MediaSpec, NotSupported, PublishMeta
from orchestrator.platforms.x.module import XModule, create_x_module


def test_x_create_and_auth():
    mod = create_x_module(dry_run=True)
    assert mod.manifest.id == "x"
    assert mod.auth_status().ok is True


def test_x_publish_text_dry():
    mod = XModule(dry_run=True)
    media = mod.prepare(MediaSpec(path="", kind="text"))
    res = mod.publish(media, PublishMeta(title="Hello", description="world", hashtags="#test"))
    assert res.external_id
    assert res.state == "published"
    assert "x.com" in res.url


def test_x_truncate():
    mod = XModule(dry_run=True, max_chars=20)
    media = mod.prepare(MediaSpec(path="", kind="text"))
    res = mod.publish(media, PublishMeta(title="A" * 50))
    assert res.state == "published"


def test_x_schedule_not_supported():
    mod = XModule(dry_run=True)
    from datetime import datetime, UTC
    with pytest.raises(NotSupported):
        mod.schedule_publish("1", datetime.now(UTC))


def test_x_delete_dry():
    mod = XModule(dry_run=True)
    assert mod.delete("123") is True


def test_x_publish_multi_image_dry(tmp_path):
    from orchestrator.platforms.base import MediaSpec, PublishMeta
    imgs = []
    for i in range(3):
        f = tmp_path / f"f{i}.jpg"
        f.write_bytes(b"\xff\xd8\xff\xd9")
        imgs.append(str(f))
    mod = XModule(dry_run=True)
    media = mod.prepare(MediaSpec(path=imgs[0], kind="image"))
    meta = PublishMeta(title="Hello", description="world")
    meta.__dict__["extra_media"] = imgs[1:]
    res = mod.publish(media, meta)
    assert res.state == "published"
    assert res.external_id


def test_x_live_status_is_remote_authoritative(monkeypatch):
    import httpx
    from orchestrator.http_client import ModuleHttpClient
    from orchestrator.platforms.x.api import XApi

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json={"data": {"id": "987", "text": "hello"}})

    http = ModuleHttpClient(
        platform="x",
        transport=httpx.MockTransport(handler),
        max_retries=1,
    )
    mod = XModule(access_token="token", http=http, dry_run=False)
    st = mod.get_status("987")
    assert st.state == "published"
    assert seen == {"method": "GET", "path": "/2/tweets/987"}


def test_http_client_accepts_multipart_files():
    import httpx
    from orchestrator.http_client import ModuleHttpClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert b"multipart/form-data" in (request.headers.get("content-type") or "").encode()
        body = request.read()
        assert b"hello.txt" in body
        return httpx.Response(200, json={"ok": True})

    http = ModuleHttpClient(
        platform="x",
        transport=httpx.MockTransport(handler),
        max_retries=1,
    )
    resp = http.request(
        "POST",
        "https://example.test/upload",
        files={"media": ("hello.txt", b"hello", "text/plain")},
        idempotent=False,
        upload=True,
    )
    assert resp.status_code == 200
