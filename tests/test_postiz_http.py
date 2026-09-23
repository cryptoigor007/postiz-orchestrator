from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.postiz import MediaRef
from orchestrator.postiz_http import HttpPostizClient


def _client(handler, token="pos_test", base="https://192-168-100-60.sslip.io"):
    return HttpPostizClient(
        base_url=base, token=token, transport=httpx.MockTransport(handler)
    )


def test_create_post_body_matches_postiz_dto():
    captured = {}

    def handler(request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json=[{"postId": "abc-123", "integration": "int-1"}])

    client = _client(handler)
    scheduled_for = datetime(2026, 9, 19, 15, 0, tzinfo=UTC)
    post = client.create_post(
        platform="telegram",
        media=MediaRef(id="media-1", path="https://host/uploads/a.mp4"),
        content={"description": "Hello", "integration_id": "int-1"},
        scheduled_for=scheduled_for,
    )

    body = captured["json"]
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/public/v1/posts")
    assert captured["auth"] == "pos_test"

    assert body["type"] == "schedule"
    assert body["shortLink"] is False
    assert body["tags"] == []
    assert body["date"] == "2026-09-19T15:00:00Z"

    entry = body["posts"][0]
    assert entry["integration"]["id"] == "int-1"
    assert entry["value"][0]["content"] == "Hello"
    assert entry["value"][0]["image"] == [
        {"id": "media-1", "path": "https://host/uploads/a.mp4"}
    ]
    assert entry["settings"] == {}

    assert post.id == "abc-123"


def test_create_post_now_when_no_schedule():
    captured = {}

    def handler(request):
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json=[{"postId": "p-now"}])

    client = _client(handler)
    client.create_post(
        platform="telegram",
        media=MediaRef(id="m1", path="https://host/u/a.mp4"),
        content={"description": "now", "integration_id": "int-1"},
        scheduled_for=None,
    )
    assert captured["json"]["type"] == "now"
    assert "date" in captured["json"]


def test_create_post_requires_integration_id():
    client = _client(lambda r: httpx.Response(200, json=[]))
    with pytest.raises(RuntimeError):
        client.create_post(
            platform="telegram",
            media=MediaRef(id="m1", path="https://host/u/a.mp4"),
            content={"description": "no integration"},
            scheduled_for=None,
        )


def test_upload_media_returns_id_and_path(tmp_path):
    media_file = tmp_path / "clip.mp4"
    media_file.write_bytes(b"fake")

    def handler(request):
        assert request.method == "POST"
        assert request.url.path.endswith("/public/v1/upload")
        return httpx.Response(
            200,
            json={
                "id": "m-42",
                "path": "https://host/uploads/clip.mp4",
                "name": "clip.mp4",
            },
        )

    client = _client(handler)
    ref = client.upload_media(str(media_file), "telegram")
    assert isinstance(ref, MediaRef)
    assert ref.id == "m-42"
    assert ref.path == "https://host/uploads/clip.mp4"


def test_upload_media_requires_path_in_response(tmp_path):
    media_file = tmp_path / "clip.mp4"
    media_file.write_bytes(b"fake")
    client = _client(lambda r: httpx.Response(200, json={"id": "m-1"}))
    with pytest.raises(RuntimeError):
        client.upload_media(str(media_file), "telegram")


def test_tls_verification_on_by_default(monkeypatch):
    monkeypatch.delenv("POSTIZ_VERIFY_TLS", raising=False)
    monkeypatch.delenv("POSTIZ_INSECURE_TLS", raising=False)
    client = _client(lambda r: httpx.Response(200, json={}))
    assert client.verify_tls is True


def test_tls_verification_can_be_disabled(monkeypatch):
    monkeypatch.setenv("POSTIZ_INSECURE_TLS", "1")
    monkeypatch.delenv("POSTIZ_VERIFY_TLS", raising=False)
    client = _client(lambda r: httpx.Response(200, json={}))
    assert client.verify_tls is False


def test_tls_verification_can_be_enabled(monkeypatch):
    monkeypatch.setenv("POSTIZ_VERIFY_TLS", "1")
    client = _client(lambda r: httpx.Response(200, json={}))
    assert client.verify_tls is True


def test_create_post_youtube_settings():
    captured = {}

    def handler(request):
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "yt-1"})

    client = _client(handler)
    client.create_post(
        platform="youtube",
        media=MediaRef(id="m1", path="p1"),
        content={
            "title": "Заголовок ролика",
            "description": "Описание",
            "hashtags": "#деньги #психология",
            "integration_id": "int-yt",
        },
        scheduled_for=datetime(2026, 9, 22, 12, 59, tzinfo=UTC),
    )
    settings = captured["json"]["posts"][0]["settings"]
    assert settings["title"] == "Заголовок ролика"
    assert settings["type"] == "public"
    assert settings["selfDeclaredMadeForKids"] == "no"
    assert {"value": "деньги", "label": "деньги"} in settings["tags"]


def test_create_post_youtube_keeps_thumbnail_and_adds_title():
    captured = {}

    def handler(request):
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "yt-2"})

    client = _client(handler)
    client.create_post(
        platform="youtube",
        media=MediaRef(id="m1", path="p1"),
        content={
            "title": "Заголовок",
            "description": "Описание",
            "integration_id": "int-yt",
            "settings": {"thumbnail": {"id": "c1", "path": "https://host/c.jpg"}},
        },
        scheduled_for=datetime(2026, 9, 22, 12, 59, tzinfo=UTC),
    )
    settings = captured["json"]["posts"][0]["settings"]
    assert settings["thumbnail"]["id"] == "c1"
    assert settings["title"] == "Заголовок"      # платформенные поля не потерялись
    assert settings["type"] == "public"


def test_post_429_is_retried(monkeypatch):
    """429 (лимит) можно повторять: ресурс не создан — повторяем и получаем успех."""
    import httpx

    from orchestrator.postiz_http import _request_with_retry

    class Stub:
        def __init__(self):
            self.calls = 0

        def request(self, method, url, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return httpx.Response(429, request=httpx.Request(method, url))
            return httpx.Response(201, json={"id": "p1"}, request=httpx.Request(method, url))

    monkeypatch.setattr("time.sleep", lambda *_: None)
    c = Stub()
    r = _request_with_retry(c, "POST", "https://x/posts")
    assert r.status_code == 201 and c.calls == 2


def test_post_500_is_not_retried(monkeypatch):
    """5xx на POST не повторяем (защита от дубликата поста)."""
    import httpx

    from orchestrator.postiz_http import _request_with_retry

    class Stub:
        def __init__(self):
            self.calls = 0

        def request(self, method, url, **kwargs):
            self.calls += 1
            return httpx.Response(500, request=httpx.Request(method, url))

    monkeypatch.setattr("time.sleep", lambda *_: None)
    c = Stub()
    r = _request_with_retry(c, "POST", "https://x/posts")
    assert r.status_code == 500 and c.calls == 1


def test_delete_retries_on_429_with_retry_after(monkeypatch):
    """P1.1: DELETE идемпотентен → 429 с Retry-After повторяется."""
    import httpx

    from orchestrator.postiz_http import HttpPostizClient

    calls = {"n": 0, "slept": []}

    class StubTransport(httpx.BaseTransport):
        def handle_request(self, request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, headers={"Retry-After": "2"},
                                      request=request)
            return httpx.Response(204, request=request)

    monkeypatch.setattr("time.sleep", lambda s: calls["slept"].append(s))
    c = HttpPostizClient(base_url="https://x", token="t", transport=StubTransport())
    c.delete_post("p1")
    assert calls["n"] == 2 and calls["slept"] == [2.0]


def test_set_status_retries_on_500(monkeypatch):
    """P1.1: PUT идемпотентен → 5xx повторяется."""
    import httpx

    from orchestrator.postiz_http import HttpPostizClient

    calls = {"n": 0}

    class StubTransport(httpx.BaseTransport):
        def handle_request(self, request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(500, request=request)
            return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr("time.sleep", lambda *_: None)
    c = HttpPostizClient(base_url="https://x", token="t", transport=StubTransport())
    c.set_status("p1", "draft")
    assert calls["n"] == 2


def test_retry_after_clamped():
    from orchestrator.postiz_http import _retry_after_seconds

    class R:
        def __init__(self, v):
            self.headers = {"retry-after": v}

    assert _retry_after_seconds(R("0")) == 1.0
    assert _retry_after_seconds(R("999")) == 60.0
    assert _retry_after_seconds(R("")) is None
    assert _retry_after_seconds(R("bogus")) is None
