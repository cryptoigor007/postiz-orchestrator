from __future__ import annotations

import httpx

from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.base import MediaSpec, PublishMeta


def client(handler):
    return ModuleHttpClient(transport=httpx.MockTransport(handler), max_retries=1)


def test_lemmy_update_and_inventory(monkeypatch):
    from orchestrator.platforms.lemmy.module import LemmyModule

    def h(req):
        if req.method == "PUT" and req.url.path.endswith("/api/v3/post"):
            return httpx.Response(200, json={"post_view": {"post": {"id": 7}}}, request=req)
        if req.method == "GET" and req.url.path.endswith("/api/v3/post/list"):
            return httpx.Response(200, json={"posts": [{"post": {"id": 7, "name": "T", "body": "B", "ap_id": "https://lemmy/a/7", "published": "2026-10-01T10:00:00Z"}}], "next_page": "abc"}, request=req)
        return httpx.Response(200, json={"post_view": {"post": {"id": 7, "name": "T", "ap_id": "https://lemmy/a/7"}}}, request=req)

    monkeypatch.setenv("LEMMY_BASE_URL", "https://lemmy.example")
    monkeypatch.setenv("LEMMY_USERNAME", "u")
    monkeypatch.setenv("LEMMY_PASSWORD", "p")
    monkeypatch.setenv("LEMMY_COMMUNITY_ID", "3")
    monkeypatch.setattr("orchestrator.platforms.lemmy.module.LemmyModule._login", lambda self, force=False: "jwt")
    m = LemmyModule(http=client(h))
    assert m.update_metadata("7", PublishMeta(title="Updated", description="Body"))
    page = m.list_remote_items(limit=10)
    assert page.items[0].external_id == "7"
    assert page.next_cursor == "abc"
    assert m.manifest.capabilities["update_metadata"] is True


def test_tiktok_upload_file_uses_sequential_content_ranges(tmp_path):
    from orchestrator.platforms.tiktok.api import TikTokApi

    media = tmp_path / 'video.mp4'
    media.write_bytes(b'a' * (11 * 1024 * 1024 + 123))

    class Resp:
        def __init__(self, status_code):
            self.status_code = status_code
            self.text = ''
            self.content = b''

    class HTTP:
        def __init__(self): self.calls=[]
        def request(self, method, url, **kwargs):
            self.calls.append((method, kwargs['headers']['Content-Range'], len(kwargs.get('content') or b''), kwargs.get('idempotent')))
            return Resp(206 if len(self.calls) == 1 else 201)

    http=HTTP()
    api=TikTokApi('tok', http=http, dry_run=False)
    assert api.upload_file('https://upload.example/video', str(media), chunk_size=5*1024*1024)
    assert len(http.calls) == 3
    assert http.calls[0][1].startswith('bytes 0-')
    assert http.calls[0][2] == 5*1024*1024
    assert http.calls[1][1].startswith('bytes 5242880-')
    assert http.calls[2][1].endswith(f'/{media.stat().st_size}')
    assert all(call[3] is True for call in http.calls)
