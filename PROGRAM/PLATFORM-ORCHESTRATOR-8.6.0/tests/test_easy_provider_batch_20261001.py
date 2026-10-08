from __future__ import annotations

import httpx

from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.base import MediaSpec, PublishMeta


def client(handler):
    return ModuleHttpClient(transport=httpx.MockTransport(handler), max_retries=1)


def test_tumblr_update_and_delete_contract():
    from orchestrator.platforms.tumblr.module import TumblrModule

    seen = []

    def handler(req):
        seen.append((req.method, req.url.path, req.content.decode()))
        if req.url.path.endswith("/post/edit"):
            return httpx.Response(200, json={"meta": {"status": 200}, "response": {"id": "1"}}, request=req)
        if req.url.path.endswith("/post/delete"):
            return httpx.Response(200, json={"meta": {"status": 200}, "response": {}}, request=req)
        return httpx.Response(200, json={"response": {"id": "1", "post_url": "https://demo.tumblr.com/post/1"}}, request=req)

    mod = TumblrModule(http=client(handler), consumer_key="ck", consumer_secret="cs", token="t", token_secret="ts", blog="demo")
    assert mod.update_metadata("1", PublishMeta(title="New", description="Body"))
    assert mod.delete("1") is True
    assert [p for _, p, _ in seen if p.endswith("/post/edit")]
    assert [p for _, p, _ in seen if p.endswith("/post/delete")]
    assert mod.manifest.capabilities["update_metadata"] is True
    assert mod.manifest.capabilities["delete"] is True


def test_devto_update_status_and_inventory(monkeypatch):
    from orchestrator.platforms.devto.module import DevtoModule

    def handler(req):
        if req.method == "PUT" and req.url.path.endswith("/articles/7"):
            return httpx.Response(200, json={"id": 7, "url": "https://dev.to/demo/seven"}, request=req)
        if req.method == "GET" and req.url.path.endswith("/articles/7"):
            return httpx.Response(200, json={"id": 7, "url": "https://dev.to/demo/seven", "published_at": "2026-10-01T10:00:00Z"}, request=req)
        if req.method == "GET" and req.url.path.endswith("/articles/me/all"):
            return httpx.Response(200, json=[{"id": 7, "title": "T", "url": "https://dev.to/demo/seven", "published_at": "2026-10-01T10:00:00Z"}], request=req)
        return httpx.Response(200, json={"username": "demo"}, request=req)

    monkeypatch.setenv("DEVTO_API_KEY", "k")
    mod = DevtoModule(http=client(handler))
    assert mod.update_metadata("7", PublishMeta(title="Updated")) is True
    assert mod.get_status("7").state == "published"
    page = mod.list_remote_items(limit=10)
    assert page.items[0].external_id == "7"
    assert page.next_cursor is None
    assert mod.manifest.capabilities["update_metadata"] is True
    assert mod.manifest.capabilities["delete"] is False


def test_listmonk_update_and_status(monkeypatch):
    from orchestrator.platforms.listmonk.module import ListmonkModule

    def handler(req):
        if req.method == "POST" and req.url.path.endswith("/campaigns"):
            return httpx.Response(200, json={"data": {"id": 11, "status": "draft"}}, request=req)
        if req.method == "PUT" and req.url.path.endswith("/campaigns/11/status"):
            return httpx.Response(200, json={"data": {"status": "running"}}, request=req)
        if req.method == "PUT" and req.url.path.endswith("/campaigns/11"):
            return httpx.Response(200, json={"data": {"id": 11, "status": "running"}}, request=req)
        if req.method == "GET" and req.url.path.endswith("/campaigns/11"):
            return httpx.Response(200, json={"data": {"id": 11, "status": "finished", "archive_url": "https://example.invalid/a/11"}}, request=req)
        return httpx.Response(200, json={"data": []}, request=req)

    monkeypatch.setenv("LISTMONK_BASE_URL", "https://listmonk.example")
    monkeypatch.setenv("LISTMONK_API_USER", "u")
    monkeypatch.setenv("LISTMONK_API_TOKEN", "t")
    mod = ListmonkModule(http=client(handler))
    result = mod.publish(mod.prepare(MediaSpec("", "text")), PublishMeta(title="T", description="B", extra={"list_ids": [1]}))
    assert result.external_id == "11"
    assert result.state == "published"
    assert mod.update_metadata("11", PublishMeta(title="T2")) is True
    assert mod.get_status("11").state == "published"
    assert mod.manifest.capabilities["update_metadata"] is True
    assert mod.manifest.capabilities["list_scheduled"] is False


def test_wordpress_update_inventory_and_delete():
    from orchestrator.platforms.wordpress.module import WordPressModule

    def handler(req):
        if req.method == "POST" and req.url.path.endswith("/posts/5"):
            return httpx.Response(200, json={"id": 5, "status": "publish", "link": "https://wp.example/p/5"}, request=req)
        if req.method == "GET" and req.url.path.endswith("/posts"):
            return httpx.Response(200, json=[{"id": 5, "status": "publish", "link": "https://wp.example/p/5", "title": {"rendered": "T"}, "content": {"rendered": "B"}, "date_gmt": "2026-10-01T10:00:00"}], request=req)
        if req.method == "DELETE" and req.url.path.endswith("/posts/5"):
            return httpx.Response(200, json={"deleted": True}, request=req)
        return httpx.Response(200, json={"id": 5, "status": "publish", "link": "https://wp.example/p/5"}, request=req)

    mod = WordPressModule(http=client(handler), base_url="https://wp.example", username="u", app_password="p")
    assert mod.update_metadata("5", PublishMeta(title="Updated")) is True
    page = mod.list_remote_items(limit=10)
    assert page.items[0].external_id == "5"
    assert page.items[0].title == "T"
    assert mod.delete("5") is True
    assert mod.manifest.capabilities["update_metadata"] is True


def test_moltbook_post_delete_reconciliation(monkeypatch):
    import httpx
    from orchestrator.platforms.moltbook.module import MoltbookModule

    monkeypatch.setenv("MOLTBOOK_API_KEY", "k")
    seen = []
    deleted = {"value": False}

    def handler(req):
        seen.append((req.method, req.url.path))
        if req.method == "GET" and req.url.path.endswith("/agents/me"):
            return httpx.Response(200, json={"agent": {"name": "bot"}}, request=req)
        if req.method == "POST" and req.url.path.endswith("/posts"):
            return httpx.Response(201, json={"post": {"id": "p1", "url": "https://www.moltbook.com/post/p1"}}, request=req)
        if req.method == "DELETE" and req.url.path.endswith("/posts/p1"):
            deleted["value"] = True
            return httpx.Response(200, json={"success": True}, request=req)
        if req.method == "GET" and req.url.path.endswith("/posts/p1"):
            return httpx.Response(404, json={"success": False}, request=req) if deleted["value"] else httpx.Response(200, json={"post": {"id": "p1"}}, request=req)
        if req.method == "GET" and req.url.path.endswith("/posts"):
            return httpx.Response(200, json={"posts": [{"id": "p1", "title": "T", "content": "B"}]}, request=req)
        raise AssertionError((req.method, req.url.path))

    mod = MoltbookModule(http=ModuleHttpClient(transport=httpx.MockTransport(handler)))
    assert mod.auth_status().ok is True
    result = mod.publish(mod.prepare(MediaSpec("", "text")), PublishMeta(title="T", description="B"))
    assert result.external_id == "p1"
    assert mod.get_status("p1").state == "published"
    assert mod.delete("p1") is True
    assert any(method == "DELETE" for method, _ in seen)
    assert mod.manifest.capabilities["publish"] is True
    assert mod.manifest.capabilities["delete"] is True



def test_nostr_bip340_event_publish_and_delete():
    from orchestrator.platforms.nostr.module import NostrModule, _N, _P, _G

    class FakeRelay:
        def __init__(self):
            self.published = []
            self.events = []
        def publish(self, event):
            self.published.append(event)
            self.events.append(event)
            return [("wss://relay.test", True, "")]
        def query(self, filters):
            ids = set(filters.get("ids") or [])
            authors = set(filters.get("authors") or [])
            rows = [e for e in self.events if (not ids or e["id"] in ids) and (not authors or e["pubkey"] in authors)]
            return rows

    fake = FakeRelay()
    mod = NostrModule(private_key=("00" * 31 + "01"), relays=["wss://relay.test"], relay_client=fake)
    assert mod.auth_status().ok is True
    result = mod.publish(mod.prepare(MediaSpec("", "text")), PublishMeta(description="hello"))
    event = fake.published[-1]
    assert result.external_id == event["id"]
    assert len(event["id"]) == 64 and len(event["pubkey"]) == 64 and len(event["sig"]) == 128
    assert event["pubkey"] == "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    # BIP340 verify: s*G == R + e*P.
    from orchestrator.platforms.nostr.module import _point_add, _point_mul, _tagged_hash
    rx = int(event["sig"][:64], 16)
    s = int(event["sig"][64:], 16)
    px = int(event["pubkey"], 16)
    py = pow((px ** 3 + 7) % _P, (_P + 1) // 4, _P)
    if py & 1:
        py = _P - py
    e = int.from_bytes(_tagged_hash("BIP0340/challenge", rx.to_bytes(32, "big") + px.to_bytes(32, "big") + bytes.fromhex(event["id"])), "big") % _N
    lhs = _point_mul(s)
    ry = pow((rx ** 3 + 7) % _P, (_P + 1) // 4, _P)
    if ry & 1:
        ry = _P - ry
    rhs = _point_add((rx, ry), _point_mul(e, (px, py)))
    assert lhs == rhs
    assert mod.get_status(result.external_id).state == "published"
    assert mod.delete(result.external_id) is True
    assert fake.published[-1]["kind"] == 5
    assert mod.manifest.publish_mode == "direct"
    assert mod.manifest.capabilities["delete"] is True


def test_wechat_draft_publish_status_inventory_and_delete(monkeypatch):
    import httpx
    from orchestrator.platforms.wechat.module import WeChatModule

    calls = []
    monkeypatch.setenv("WECHAT_APP_ID", "app")
    monkeypatch.setenv("WECHAT_APP_SECRET", "secret")
    state = {"published": False}

    def handler(req):
        calls.append((req.method, req.url.path))
        if req.url.path.endswith("/cgi-bin/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200}, request=req)
        if req.url.path.endswith("/cgi-bin/draft/count"):
            return httpx.Response(200, json={"total": 0, "errcode": 0}, request=req)
        if req.url.path.endswith("/cgi-bin/draft/add"):
            return httpx.Response(200, json={"media_id": "draft1", "errcode": 0}, request=req)
        if req.url.path.endswith("/cgi-bin/freepublish/submit"):
            return httpx.Response(200, json={"publish_id": "pub1", "errcode": 0}, request=req)
        if req.url.path.endswith("/cgi-bin/freepublish/get"):
            state["published"] = True
            return httpx.Response(200, json={"publish_status": 0, "article_id": "art1", "article_detail": {"item": [{"article_url": "https://mp.weixin.qq.com/s/art1"}]}, "errcode": 0}, request=req)
        if req.url.path.endswith("/cgi-bin/freepublish/batchget"):
            return httpx.Response(200, json={"total_count": 1, "item": [{"article_id": "art1", "content": {"news_item": [{"title": "T", "digest": "D", "url": "https://mp.weixin.qq.com/s/art1"}]}}], "errcode": 0}, request=req)
        if req.url.path.endswith("/cgi-bin/freepublish/delete"):
            assert state["published"] is True
            assert b'"article_id": "art1"' in req.content or b'"article_id":"art1"' in req.content
            return httpx.Response(200, json={"errcode": 0}, request=req)
        raise AssertionError((req.method, req.url.path))

    mod = WeChatModule(http=ModuleHttpClient(transport=httpx.MockTransport(handler)))
    assert mod.auth_status().ok is True
    result = mod.publish(mod.prepare(MediaSpec("", "text")), PublishMeta(title="T", description="B", extra={"content_html": "<p>Body</p>", "thumb_media_id": "thumb1"}))
    assert result.external_id == "pub1"
    assert result.state == "uploaded"
    status = mod.get_status("pub1")
    assert status.state == "published"
    assert status.url.endswith("art1")
    page = mod.list_remote_items(limit=10)
    assert page.items[0].external_id == "art1"
    assert mod.delete("publish:pub1") is True
    assert any(path.endswith("/cgi-bin/freepublish/delete") for _, path in calls)
    assert mod.manifest.capabilities["publish"] is True
    assert mod.manifest.capabilities["delete"] is True


def test_kick_native_channel_metadata_and_livestream_inventory(monkeypatch):
    import httpx
    from orchestrator.platforms.kick.module import KickModule
    monkeypatch.setenv("KICK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("KICK_BROADCASTER_USER_ID", "42")
    seen = []
    def handler(req):
        seen.append((req.method, req.url.path))
        if req.method == "GET" and req.url.path.endswith("/channels"):
            return httpx.Response(200, json={"data": [{"broadcaster_user_id": "42", "name": "Demo"}]}, request=req)
        if req.method == "PATCH" and req.url.path.endswith("/channels"):
            return httpx.Response(200, json={"data": {"broadcaster_user_id": "42", "stream_title": "Updated"}}, request=req)
        if req.method == "GET" and req.url.path.endswith("/livestreams"):
            return httpx.Response(200, json={"data": [{"id": "ls1", "session_title": "Live", "is_live": True}]}, request=req)
        raise AssertionError((req.method, req.url.path))
    mod = KickModule(http=ModuleHttpClient(transport=httpx.MockTransport(handler)))
    assert mod.auth_status().ok is True
    assert mod.update_metadata("42", PublishMeta(title="Updated")) is True
    page = mod.list_remote_items(limit=10)
    assert page.items[0].external_id == "ls1"
    assert mod.get_status("42").state == "published"
    assert mod.manifest.capabilities["publish"] is False
    assert mod.manifest.capabilities["update_metadata"] is True


def test_mewe_group_publish_schedule_and_inventory(monkeypatch):
    import httpx
    from orchestrator.platforms.mewe.module import MeWeModule

    monkeypatch.setenv("MEWE_API_TOKEN", "tok")
    monkeypatch.setenv("MEWE_APP_ID", "app")
    monkeypatch.setenv("MEWE_GROUP_ID", "g1")

    def handler(req):
        if req.method == "GET" and req.url.path.endswith("/api/dev/me"):
            return httpx.Response(200, json={"userId": "u1", "username": "demo"}, request=req)
        if req.method == "POST" and req.url.path.endswith("/api/dev/group/g1/post"):
            assert req.headers["X-App-Id"] == "app"
            import json
            body = json.loads(req.content.decode("utf-8"))
            assert body["text"] == "hello"
            assert body["schedule"] == 1770000000000
            return httpx.Response(200, json={"postId": "p1"}, request=req)
        if req.method == "GET" and req.url.path.endswith("/api/dev/group/g1/postsfeed"):
            return httpx.Response(200, json={"posts": [{"id": "p1", "text": "hello", "status": "scheduled", "createdAt": 1770000000000}], "nextPage": "n2"}, request=req)
        raise AssertionError((req.method, req.url.path))

    mod = MeWeModule(http=ModuleHttpClient(transport=httpx.MockTransport(handler)))
    assert mod.auth_status().ok is True
    result = mod.publish(mod.prepare(MediaSpec("", "text")), PublishMeta(title="ignored", extra={"text": "hello", "schedule": 1770000000000}))
    assert result.external_id == "p1"
    assert result.state == "scheduled"
    status = mod.get_status("p1")
    assert status.state == "scheduled"
    page = mod.list_remote_items(limit=10)
    assert page.items[0].external_id == "p1"
    assert page.next_cursor == "n2"
    assert mod.manifest.capabilities["publish"] is True
    assert mod.manifest.capabilities["schedule_publish"] is True
    assert mod.manifest.capabilities["delete"] is False
