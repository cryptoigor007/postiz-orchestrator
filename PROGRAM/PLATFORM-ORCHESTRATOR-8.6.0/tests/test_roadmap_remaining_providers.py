from __future__ import annotations

import httpx

from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.base import MediaSpec, PublishMeta


def client(handler):
    return ModuleHttpClient(transport=httpx.MockTransport(handler), max_retries=1)


def test_whop_feed_content_item_publish(monkeypatch):
    from orchestrator.platforms.whop.module import WhopModule

    monkeypatch.setenv("WHOP_API_KEY", "k")
    monkeypatch.setenv("WHOP_USER_ID", "user_1")
    monkeypatch.setenv("WHOP_EXPERIENCE_ID", "exp_1")

    def handler(req):
        if req.method == "POST" and req.url.path == "/v5/app/feed_content_items":
            import json
            body = json.loads(req.content.decode("utf-8"))
            assert body["experience_id"] == "exp_1"
            assert body["user_id"] == "user_1"
            assert body["metadata"]["title"] == "Hello"
            return httpx.Response(201, json={"id": "fci_1"}, request=req)
        raise AssertionError((req.method, req.url.path))

    mod = WhopModule(http=client(handler))
    result = mod.publish(mod.prepare(MediaSpec("", "text")), PublishMeta(title="Hello", description="Body"))
    assert result.external_id == "fci_1"
    assert result.state == "published"
    assert mod.manifest.capabilities["publish"] is True
    assert mod.manifest.capabilities["delete"] is False


def test_snapchat_story_publish_and_inventory(monkeypatch):
    from orchestrator.platforms.snapchat.module import SnapchatModule

    monkeypatch.setenv("SNAPCHAT_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("SNAPCHAT_PROFILE_ID", "profile1")

    def handler(req):
        if req.method == "GET" and req.url.path.endswith("/public_profiles/profile1"):
            return httpx.Response(200, json={"request_status": "SUCCESS", "profile": {"id": "profile1"}}, request=req)
        if req.method == "POST" and req.url.path.endswith("/stories"):
            import json
            body = json.loads(req.content.decode("utf-8"))
            assert body["media_id"] == "media1"
            return httpx.Response(200, json={"request_status": "SUCCESS", "story_id": "story1"}, request=req)
        if req.method == "GET" and req.url.path.endswith("/stories"):
            return httpx.Response(200, json={"request_status": "SUCCESS", "stories": [{"story": {"id": "story1", "created_at": "2026-10-01T10:00:00Z", "type": "PUBLIC_STORY"}}], "paging": {"next_page_id": "next"}}, request=req)
        raise AssertionError((req.method, req.url.path))

    mod = SnapchatModule(http=client(handler))
    assert mod.auth_status().ok is True
    result = mod.publish(mod.prepare(MediaSpec("", "video")), PublishMeta(extra={"media_id": "media1", "ttl": "TWO_DAYS"}))
    assert result.external_id == "story1"
    assert result.state == "published"
    page = mod.list_remote_items(limit=10)
    assert page.items[0].external_id == "story1"
    assert page.next_cursor == "next"
    assert mod.get_status("story1").state == "published"
    assert mod.manifest.capabilities["publish"] is True
    assert mod.manifest.capabilities["delete"] is False
