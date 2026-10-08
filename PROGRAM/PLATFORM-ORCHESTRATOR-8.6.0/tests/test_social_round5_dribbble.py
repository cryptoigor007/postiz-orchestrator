from pathlib import Path
import httpx
from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.base import MediaSpec, PublishMeta


def client(handler):
    return ModuleHttpClient(platform="dribbble", transport=httpx.MockTransport(handler), max_retries=1)


def test_dribbble_publish_update_status_delete_and_inventory(tmp_path: Path):
    from orchestrator.platforms.dribbble.module import DribbbleModule
    p = tmp_path / "shot.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + (400).to_bytes(4, "big") + (300).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
    def h(req):
        if req.method == "GET" and req.url.path.endswith("/user"):
            return httpx.Response(200, json={"username": "demo"}, request=req)
        if req.method == "POST" and req.url.path.endswith("/shots"):
            assert b"shot.png" in req.content
            return httpx.Response(202, headers={"Location": "https://api.dribbble.com/v2/shots/77"}, request=req)
        if req.method == "PUT" and req.url.path.endswith("/shots/77"):
            return httpx.Response(200, json={"id": 77}, request=req)
        if req.method == "GET" and req.url.path.endswith("/shots/77"):
            return httpx.Response(200, json={"id": 77, "html_url": "https://dribbble.com/shots/77", "title": "T"}, request=req)
        if req.method == "DELETE" and req.url.path.endswith("/shots/77"):
            return httpx.Response(204, request=req)
        if req.method == "GET" and req.url.path.endswith("/user/shots"):
            return httpx.Response(200, json=[{"id": 77, "html_url": "https://dribbble.com/shots/77", "title": "T"}], request=req)
        return httpx.Response(404, request=req)
    m = DribbbleModule(http=client(h), access_token="tok")
    assert m.auth_status().ok
    r = m.publish(m.prepare(MediaSpec(str(p), "image")), PublishMeta(title="T"))
    assert r.external_id == "77"
    assert r.state == "processing"
    assert m.update_metadata("77", PublishMeta(title="T2"))
    assert m.get_status("77").state == "published"
    assert m.list_remote_items(limit=10).items[0].external_id == "77"
    assert m.delete("77")
