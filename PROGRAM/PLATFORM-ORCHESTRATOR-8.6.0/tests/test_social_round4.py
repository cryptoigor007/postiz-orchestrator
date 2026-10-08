from __future__ import annotations
import hashlib,hmac,json
from pathlib import Path
import httpx
from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.base import MediaSpec, PublishMeta

def client(handler):
    return ModuleHttpClient(transport=httpx.MockTransport(handler), max_retries=1)

def test_beehiiv_update_delete(monkeypatch):
    from orchestrator.platforms.beehiiv.module import BeehiivModule
    calls=[]
    def h(req):
        calls.append(req.method)
        return httpx.Response(200 if req.method=="PATCH" else 204, json={} if req.method=="PATCH" else None, request=req)
    monkeypatch.setenv("BEEHIIV_PUBLICATION_ID","pub_1")
    m=BeehiivModule(token_provider=lambda *_:"tok", http=client(h))
    assert m.update_metadata("post_1", PublishMeta(title="New"))
    assert m.delete("post_1")
    assert calls==["PATCH","DELETE"]

def test_discord_edit_delete():
    from orchestrator.platforms.discord.module import DiscordModule
    paths=[]
    def h(req):
        paths.append((req.method,req.url.path))
        return httpx.Response(200 if req.method=="PATCH" else 204, json={"id":"1"} if req.method=="PATCH" else None, request=req)
    m=DiscordModule(http=client(h),webhook_url="https://discord.com/api/webhooks/x/y")
    assert m.update_message("discord:123",{"text":"edited"})
    assert m.delete_message("discord:123")
    assert paths[0][1].endswith("/messages/123")

def test_slack_update_delete(monkeypatch):
    from orchestrator.platforms.slack.module import SlackModule
    seen=[]
    def h(req):
        seen.append(req.url.path)
        return httpx.Response(200,json={"ok":True,"channel":"C1","ts":"1"},request=req)
    m=SlackModule(http=client(h),token_provider=lambda *_:"tok",channel="C1")
    assert m.update_message("C1","1",{"text":"new"})["ok"]
    assert m.delete_message("C1","1")["ok"]
    assert seen==["/api/chat.update","/api/chat.delete"]

def test_line_multicast_validate_webhook(monkeypatch):
    from orchestrator.platforms.line.module import LineModule
    seen=[]
    def h(req):
        seen.append(req.url.path)
        return httpx.Response(200,json={},request=req)
    secret="sec"; body=b'{"events":[]}'
    m=LineModule(http=client(h),token_provider=lambda *_:"tok",channel_secret=secret)
    assert m.send_multicast(["U1","U2"],{"text":"hi"})=={}
    assert m.validate_push({"text":"hi"})=={}
    assert m.set_webhook_endpoint("https://example.test/line")=={}
    assert m.verify_webhook(base64sig:=__import__('base64').b64encode(hmac.new(secret.encode(),body,hashlib.sha256).digest()).decode(),body)
    assert seen[-1]=="/v2/bot/channel/webhook/endpoint"

def test_messenger_auth_attachment(monkeypatch):
    from orchestrator.platforms.messenger.module import MessengerModule
    def h(req):
        if req.method=="GET": return httpx.Response(200,json={"id":"p1","name":"Page"},request=req)
        return httpx.Response(200,json={"message_id":"m1"},request=req)
    m=MessengerModule(http=client(h),token_provider=lambda *_:"tok",page_id="p1")
    assert m.auth_status().ok
    out=m.send_message("u1",{"attachment":{"type":"image","payload":{"url":"https://e/x.jpg"}}})
    assert out["message_id"]=="m1"

def test_instagram_messaging_auth_attachment(monkeypatch):
    from orchestrator.platforms.instagram_messaging.module import InstagramMessagingModule
    def h(req):
        if req.method=="GET": return httpx.Response(200,json={"id":"ig1","username":"demo"},request=req)
        return httpx.Response(200,json={"message_id":"m2"},request=req)
    m=InstagramMessagingModule(http=client(h),token_provider=lambda *_:"tok",ig_user_id="ig1")
    assert m.auth_status().ok
    out=m.send_message("u1",{"attachment":{"type":"image","payload":{"url":"https://e/x.jpg"}}})
    assert out["message_id"]=="m2"

def test_vk_update_and_reconcile():
    from orchestrator.platforms.vk.module import VKModule
    seen=[]
    def h(req):
        # ModuleHttpClient encodes the method name in POST form data; return by URL.
        seen.append(req.url.path)
        if req.url.path.endswith("/video.get"):
            return httpx.Response(200,json={"response":{"items":[{"id":2,"owner_id":-9,"title":"x"}]}},request=req)
        if req.url.path.endswith("/wall.edit"):
            return httpx.Response(200,json={"response":1},request=req)
        return httpx.Response(200,json={"response":{}},request=req)
    m=VKModule(http=client(h),access_token="tok",group_id="9",dry_run=False)
    assert m.update_metadata("-9_2",PublishMeta(title="T",description="D"))
    assert m.get_status("-9_2").state=="published"

def test_telegram_media_update():
    from orchestrator.platforms.telegram.module import TelegramModule
    def h(req):
        if req.url.path.endswith("/editMessageMedia"):
            return httpx.Response(200,json={"ok":True,"result":{"message_id":7}},request=req)
        return httpx.Response(200,json={"ok":True,"result":{"id":1,"username":"bot"}},request=req)
    m=TelegramModule("tok","-1001",http=client(h))
    assert m.update_media("tg:7",media_type="photo",media="file_123",caption="new")

def test_youtube_processing_failure_mapping(monkeypatch):
    from orchestrator.platforms.youtube.module import YouTubeModule
    class A:
        def videos_list(self,ids):
            return {"items":[{"id":"v1","status":{"privacyStatus":"private","uploadStatus":"uploaded"},"processingDetails":{"processingStatus":"failed","processingFailureReason":"codec"}}]}
    m=YouTubeModule(lambda:"tok",dry_run=False,http=client(lambda req:httpx.Response(200,json={},request=req)))
    m._api=A()
    st=m.get_status("v1")
    assert st.state=="failed" and st.error=="codec"

def test_tiktok_direct_post_flow(tmp_path):
    from orchestrator.platforms.tiktok.module import TikTokModule
    p=tmp_path/"a.mp4"; p.write_bytes(b"123456")
    seen=[]
    def h(req):
        seen.append((req.method,req.url.path,dict(req.headers)))
        if req.url.path.endswith("creator_info/query/"):
            return httpx.Response(200,json={"data":{"creator_username":"demo","privacy_level_options":["PUBLIC_TO_EVERYONE"]}},request=req)
        if req.url.path.endswith("video/init/"):
            return httpx.Response(200,json={"data":{"publish_id":"pub1","upload_url":"https://up.example/u"}},request=req)
        if req.url.path=="/u":
            return httpx.Response(200,json={},request=req)
        if req.url.path.endswith("status/fetch/"):
            return httpx.Response(200,json={"data":{"status":"PUBLISH_COMPLETE"}},request=req)
        return httpx.Response(200,json={},request=req)
    m=TikTokModule(access_token="tok",http=client(h),dry_run=False,publish_mode="direct")
    r=m.publish(m.prepare(MediaSpec(str(p))),PublishMeta(title="Hello"))
    assert r.external_id=="pub1"
    assert m.get_status("pub1").state=="published"
    assert any(path.endswith("video/init/") for _,path,_ in seen)
