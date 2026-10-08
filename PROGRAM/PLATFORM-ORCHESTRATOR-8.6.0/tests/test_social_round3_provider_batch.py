from __future__ import annotations
import hashlib, hmac
from pathlib import Path
import httpx
from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.base import MediaSpec, PublishMeta


def client(handler):
    return ModuleHttpClient(transport=httpx.MockTransport(handler), max_retries=1)


def test_linkedin_partial_update_and_delete():
    from orchestrator.platforms.linkedin.module import LinkedInModule
    seen = []
    def h(req):
        seen.append((req.method, req.url.path, dict(req.headers), req.content))
        if req.method == "POST" and "/rest/posts/" in req.url.path:
            return httpx.Response(204, request=req)
        if req.method == "DELETE":
            return httpx.Response(204, request=req)
        return httpx.Response(200, json={"id":"urn:li:share:1","lifecycleState":"PUBLISHED"}, request=req)
    m = LinkedInModule(http=client(h), access_token="tok", author_urn="urn:li:person:1")
    assert m.update_metadata("urn:li:share:1", PublishMeta(description="Updated"))
    assert m.delete("urn:li:share:1")
    post = [x for x in seen if x[0] == "POST"][0]
    assert post[2]["x-restli-method"] == "PARTIAL_UPDATE"
    assert b'"commentary":"Updated"' in post[3]
    assert m.manifest.capabilities["update_metadata"] is True


def test_x_chunked_video_upload(tmp_path):
    from orchestrator.platforms.x.api import XApi
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"x" * 10)
    calls = []
    def h(req):
        calls.append((req.method, req.url.path, dict(req.url.params)))
        cmd = req.url.params.get("command")
        if cmd == "INIT":
            return httpx.Response(200, json={"media_id_string":"55"}, request=req)
        if cmd == "APPEND":
            return httpx.Response(204, request=req)
        if cmd == "FINALIZE":
            return httpx.Response(200, json={"media_id_string":"55","processing_info":{"state":"pending"}}, request=req)
        if cmd == "STATUS":
            return httpx.Response(200, json={"media_id_string":"55","processing_info":{"state":"succeeded"}}, request=req)
        return httpx.Response(200, json={}, request=req)
    api = XApi("tok", http=client(h), dry_run=False)
    assert api.upload_media(str(p), media_type="video/mp4", chunk_size=4) == "55"
    assert api.media_status("55")["processing_info"]["state"] == "succeeded"
    assert any(x[2].get("command") == "APPEND" for x in calls)


def test_viber_broadcast_user_details_and_webhook_flags():
    from orchestrator.platforms.viber.module import ViberModule
    seen=[]
    def h(req):
        seen.append((req.url.path, req.content))
        if req.url.path.endswith("get_user_details"):
            return httpx.Response(200, json={"status":0,"id":"u1","name":"User"}, request=req)
        return httpx.Response(200, json={"status":0}, request=req)
    m=ViberModule(http=client(h), token_provider=lambda *_:"tok")
    assert m.broadcast_message(["u1","u2"], {"type":"text","text":"hi"})["status"] == 0
    assert m.get_user_details("u1")["id"] == "u1"
    m.set_webhook("https://example.com/hook", ["message"], send_name=False, send_photo=True)
    body = b'{"event":"message"}'
    sig = hmac.new(b"tok", body, hashlib.sha256).hexdigest()
    assert m.verify_webhook({"X-Viber-Content-Signature":sig}, body)
    assert any(b'"broadcast_list"' in body for _, body in seen)


def test_threads_image_delete_and_quota():
    from orchestrator.platforms.threads.module import ThreadsModule
    def h(req):
        path=req.url.path
        if req.method=="POST" and path.endswith("/threads"):
            return httpx.Response(200,json={"id":"c1"},request=req)
        if req.method=="GET" and path.endswith("/c1"):
            return httpx.Response(200,json={"id":"c1","status":"FINISHED"},request=req)
        if req.method=="POST" and path.endswith("/threads_publish"):
            return httpx.Response(200,json={"id":"p1"},request=req)
        if req.method=="GET" and path.endswith("/p1"):
            return httpx.Response(200,json={"id":"p1","permalink":"https://threads/p1"},request=req)
        if req.method=="DELETE" and path.endswith("/p1"):
            return httpx.Response(200,json={},request=req)
        if path.endswith("threads_publishing_limit"):
            return httpx.Response(200,json={"quota_usage":2,"quota_config":{"quota_total":250}},request=req)
        return httpx.Response(200,json={},request=req)
    m=ThreadsModule(http=client(h), access_token="tok", user_id="u1", dry_run=False, media_host=type("H",(),{"upload":lambda self,path,prefix: "https://cdn.example/a.jpg"})())
    r=m.publish(m.prepare(MediaSpec("/tmp/a.jpg","image")), PublishMeta(description="hello"))
    assert r.external_id=="p1"
    assert m.delete("p1")
    q=m.get_quota()
    assert q.remaining==248 and q.limit==250
    assert m.manifest.capabilities["image"] and m.manifest.capabilities["delete"]


def test_whatsapp_local_media_read_receipt_and_signature(tmp_path):
    from orchestrator.platforms.whatsapp.module import WhatsAppModule
    p=tmp_path/"a.jpg"; p.write_bytes(b"abc")
    calls=[]
    def h(req):
        calls.append((req.method, req.url.path, req.content))
        if req.url.path.endswith("/media"):
            return httpx.Response(200,json={"id":"m1"},request=req)
        return httpx.Response(200,json={"messages":[{"id":"wamid.1"}]},request=req)
    m=WhatsAppModule(http=client(h), token_provider=lambda *_:"tok", phone_number_id="123")
    out=m.send_message("7999", {"type":"image", "image":{"path":str(p)}})
    assert out["messages"][0]["id"] == "wamid.1"
    assert m.mark_read("wamid.1")["messages"][0]["id"] == "wamid.1"
    body=b'{"entry":[]}'
    sig="sha256="+hmac.new(b"appsecret",body,hashlib.sha256).hexdigest()
    assert m.verify_webhook_signature("appsecret",sig,body)
    assert any(path.endswith("/media") for _,path,_ in calls)


def test_instagram_image_carousel_and_inventory():
    from orchestrator.platforms.instagram.module import InstagramModule
    def h(req):
        path=req.url.path
        if path.endswith("/media") and req.method=="POST":
            return httpx.Response(200,json={"id":"c1"},request=req)
        if path.endswith("/media_publish"):
            return httpx.Response(200,json={"id":"m1"},request=req)
        if path.endswith("/c1"):
            return httpx.Response(200,json={"status_code":"FINISHED"},request=req)
        if path.endswith("/m1"):
            return httpx.Response(200,json={"permalink":"https://instagram/m1"},request=req)
        if path.endswith("/u1/media"):
            return httpx.Response(200,json={"data":[{"id":"m1","permalink":"https://instagram/m1"}]},request=req)
        return httpx.Response(200,json={"id":"u1","username":"demo"},request=req)
    m=InstagramModule(http=client(h), access_token="tok", ig_user_id="u1", dry_run=False, media_host=type("H",(),{"upload":lambda self,path,prefix: "https://cdn.example/a.jpg"})(), poll_max=1)
    r=m.publish(m.prepare(MediaSpec("/tmp/a.jpg","image")), PublishMeta(description="hello"))
    assert r.external_id=="m1"
    assert m.list_remote(limit=5)[0]["id"]=="m1"
    c=m.publish(m.prepare(MediaSpec("/tmp/a.jpg","image")), PublishMeta(description="car", extra={"carousel_image_urls":["https://a/1.jpg","https://a/2.jpg"]}))
    assert c.external_id=="m1"
    assert m.manifest.capabilities["image"] is True


def test_facebook_video_metadata_and_authoritative_status():
    from orchestrator.platforms.facebook.module import FacebookModule
    def h(req):
        if req.method=="POST" and req.url.path.endswith("/55"):
            return httpx.Response(200,json={"success":True},request=req)
        if req.method=="GET" and req.url.path.endswith("/55"):
            return httpx.Response(200,json={"id":"55","status":"published","published":True,"permalink_url":"https://facebook/55"},request=req)
        return httpx.Response(200,json={"id":"1","name":"Page"},request=req)
    m=FacebookModule(http=client(h), page_token="tok", page_id="p1", dry_run=False)
    assert m.update_metadata("55", PublishMeta(title="New",description="Body"))
    assert m.get_status("55").state=="published"
    assert m.manifest.capabilities["update_metadata"] is True
    assert m.manifest.status_authority=="authoritative"
