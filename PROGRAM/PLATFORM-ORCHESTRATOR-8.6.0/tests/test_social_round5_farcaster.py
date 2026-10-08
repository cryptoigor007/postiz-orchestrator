import httpx
from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.base import MediaSpec, PublishMeta


def client(handler):
    return ModuleHttpClient(platform="farcaster", transport=httpx.MockTransport(handler), max_retries=1)


def test_farcaster_partner_publish_status_delete_and_inventory():
    from orchestrator.platforms.farcaster.module import FarcasterModule
    def h(req):
        if req.method == "GET" and req.url.path.endswith("/user/bulk"):
            return httpx.Response(200, json={"users": [{"fid": 123, "username": "demo"}]}, request=req)
        if req.method == "POST" and req.url.path.endswith("/farcaster/cast"):
            return httpx.Response(200, json={"cast": {"hash": "0xabc", "url": "https://warpcast.com/demo/0xabc", "text": "Hello"}}, request=req)
        if req.method == "GET" and req.url.path.endswith("/farcaster/cast"):
            return httpx.Response(200, json={"cast": {"hash": "0xabc", "url": "https://warpcast.com/demo/0xabc", "text": "Hello"}}, request=req)
        if req.method == "DELETE" and req.url.path.endswith("/farcaster/cast/"):
            return httpx.Response(200, json={"success": True}, request=req)
        if req.method == "GET" and req.url.path.endswith("/farcaster/feed/user/casts"):
            return httpx.Response(200, json={"casts": [{"hash": "0xabc", "url": "https://warpcast.com/demo/0xabc", "text": "Hello", "timestamp": "2026-10-01T12:00:00Z"}], "next": {"cursor": "next"}}, request=req)
        return httpx.Response(404, request=req)
    m = FarcasterModule(http=client(h), api_key="key", signer_uuid="signer", fid="123")
    assert m.auth_status().ok
    r = m.publish(m.prepare(MediaSpec("", "text")), PublishMeta(description="Hello"))
    assert r.external_id == "0xabc"
    assert m.get_status("0xabc").state == "published"
    assert m.list_remote_items(limit=10).next_cursor == "next"
    assert m.delete("0xabc")
    assert m.manifest.publish_mode == "partner"
