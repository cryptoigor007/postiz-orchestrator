import httpx
from orchestrator.http_client import ModuleHttpClient


def client(handler):
    return ModuleHttpClient(platform="twitch", transport=httpx.MockTransport(handler), max_retries=1)


def test_twitch_clips_auth_create_status_and_inventory():
    from orchestrator.platforms.twitch.module import TwitchModule
    def h(req):
        if req.method == "GET" and req.url.path.endswith("/users"):
            return httpx.Response(200, json={"data": [{"id": "42", "login": "demo", "display_name": "Demo"}]}, request=req)
        if req.method == "POST" and req.url.path.endswith("/clips") and not req.url.path.endswith("/videos/clips"):
            assert req.url.params.get("broadcaster_id") == "42"
            return httpx.Response(202, json={"data": [{"id": "clip1", "edit_url": "https://clips.twitch.tv/edit/clip1"}]}, request=req)
        if req.method == "POST" and req.url.path.endswith("/videos/clips"):
            return httpx.Response(202, json={"data": [{"id": "vodclip"}]}, request=req)
        if req.method == "GET" and req.url.path.endswith("/clips") and req.url.params.get("id") == "clip1":
            return httpx.Response(200, json={"data": [{"id": "clip1", "url": "https://clips.twitch.tv/clip1", "title": "Test", "duration": 30, "thumbnail_url": "https://img"}]}, request=req)
        if req.method == "GET" and req.url.path.endswith("/clips"):
            return httpx.Response(200, json={"data": [{"id": "clip1", "url": "https://clips.twitch.tv/clip1", "title": "Test", "duration": 30, "thumbnail_url": "https://img"}], "pagination": {"cursor": "next"}}, request=req)
        return httpx.Response(404, request=req)
    m = TwitchModule(http=client(h), client_id="cid", access_token="tok", broadcaster_id="42")
    assert m.auth_status().ok
    r = m.create_clip(title="Test", duration=30)
    assert r.external_id == "clip1"
    assert m.get_status("clip1").state == "published"
    assert m.list_remote_items(limit=10).next_cursor == "next"
    assert m.create_clip_from_vod(vod_id="vod1", vod_offset=10).external_id == "vodclip"
