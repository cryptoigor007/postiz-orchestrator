from __future__ import annotations
import httpx, hashlib, hmac, json
from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.bluesky.module import BlueskyModule
from orchestrator.platforms.viber.module import ViberModule


def c(handler): return ModuleHttpClient(transport=httpx.MockTransport(handler), max_retries=1)

def test_bluesky_publish(monkeypatch):
    def h(req):
        if 'createSession' in str(req.url):
            return httpx.Response(200,json={'accessJwt':'jwt','did':'did:plc:1'},request=req)
        if 'com.atproto.repo.createRecord' in str(req.url):
            return httpx.Response(200,json={'uri':'at://did:plc:1/app.bsky.feed.post/abc','cid':'c'},request=req)
        return httpx.Response(200,json={'posts':[{'uri':'at://did:plc:1/app.bsky.feed.post/abc'}]},request=req)
    monkeypatch.setenv('BLUESKY_HANDLE','a.test'); monkeypatch.setenv('BLUESKY_APP_PASSWORD','pw')
    m=BlueskyModule(http=c(h))
    from orchestrator.platforms.base import MediaSpec, PublishMeta
    r=m.publish(m.prepare(MediaSpec(path='',kind='text')),PublishMeta(title='hello'))
    assert r.external_id.endswith('/abc')
    assert m.get_status(r.external_id).state=='published'

def test_viber_webhook_signature():
    body=b'{"event":"message"}'; token='tok'
    sig=hmac.new(token.encode(),body,hashlib.sha256).hexdigest()
    m=ViberModule(token_provider=lambda *_:token, http=c(lambda req:httpx.Response(200,json={'status':0},request=req)))
    assert m.verify_webhook({'X-Viber-Content-Signature':sig},body)
    assert not m.verify_webhook({'X-Viber-Content-Signature':'bad'},body)


def test_beehiiv_create_and_async_status(monkeypatch):
    import httpx
    from orchestrator.http_client import ModuleHttpClient
    from orchestrator.platforms.beehiiv.module import BeehiivModule
    from orchestrator.platforms.base import MediaSpec, PublishMeta
    calls=[]
    def h(req):
        calls.append((req.method, str(req.url)))
        if req.method == "POST":
            return httpx.Response(201, json={"data":{"id":"post_1","preview_url":"https://app.beehiiv.com/posts/post_1/preview"}}, request=req)
        if str(req.url).endswith("/publications/pub_1/posts/post_1"):
            return httpx.Response(200, json={"data":{"id":"post_1","status":"confirmed","web_url":"https://example.com/post-1"}}, request=req)
        return httpx.Response(200, json={"data":{"id":"pub_1","name":"Demo"}}, request=req)
    monkeypatch.setenv("BEEHIIV_PUBLICATION_ID", "pub_1")
    m=BeehiivModule(token_provider=lambda *_:"tok", http=ModuleHttpClient(transport=httpx.MockTransport(h), max_retries=1))
    r=m.publish(m.prepare(MediaSpec(path="",kind="text")), PublishMeta(title="Hello", description="Body"))
    assert r.external_id == "post_1"
    assert r.state == "processing"
    assert m.get_status("post_1").state == "published"
    assert any(method == "POST" for method,_ in calls)


def test_mastodon_publish_status_and_delete(monkeypatch):
    from orchestrator.platforms.mastodon.module import MastodonModule
    calls=[]
    def h(req):
        calls.append((req.method,str(req.url)))
        if req.method == "GET" and req.url.path.endswith("/accounts/verify_credentials"):
            return httpx.Response(200,json={"acct":"demo@example.social"},request=req)
        if req.method == "POST" and req.url.path.endswith("/api/v1/statuses"):
            return httpx.Response(200,json={"id":"77","url":"https://social.example/@demo/77"},request=req)
        if req.method == "GET" and req.url.path.endswith("/api/v1/statuses/77"):
            return httpx.Response(200,json={"id":"77","url":"https://social.example/@demo/77"},request=req)
        if req.method == "DELETE":
            return httpx.Response(200,json={},request=req)
        return httpx.Response(200,json={},request=req)
    monkeypatch.setenv("MASTODON_ACCESS_TOKEN","tok")
    m=MastodonModule(http=c(h), base_url="https://social.example")
    assert m.auth_status().ok
    r=m.publish(m.prepare(__import__('orchestrator.platforms.base',fromlist=['MediaSpec']).MediaSpec(path="",kind="text")), __import__('orchestrator.platforms.base',fromlist=['PublishMeta']).PublishMeta(description="hello"))
    assert r.external_id == "77"
    assert m.get_status("77").state == "published"
    assert m.delete("77") is True


def test_slack_discord_line_whatsapp_message_paths(monkeypatch):
    from orchestrator.platforms.slack.module import SlackModule
    from orchestrator.platforms.discord.module import DiscordModule
    from orchestrator.platforms.line.module import LineModule
    from orchestrator.platforms.whatsapp.module import WhatsAppModule
    def h(req):
        if "slack.com/api/auth.test" in str(req.url): return httpx.Response(200,json={"ok":True,"team":"T"},request=req)
        if "slack.com/api/chat.postMessage" in str(req.url): return httpx.Response(200,json={"ok":True,"ts":"1"},request=req)
        if req.url.path.endswith("/v2/bot/info"): return httpx.Response(200,json={"displayName":"LINE"},request=req)
        if req.url.path.endswith("/message/push"): return httpx.Response(200,json={},request=req)
        if req.url.path.endswith("/v26.0/123") or req.url.path.endswith("/v26.0/456"): return httpx.Response(200,json={"id":"123"},request=req)
        if req.url.path.endswith("/messages"): return httpx.Response(200,json={"messages":[{"id":"wamid.1"}]},request=req)
        if "discord.com/api/webhooks" in str(req.url): return httpx.Response(200,json={"id":"d1","name":"hook"},request=req)
        return httpx.Response(200,json={},request=req)
    monkeypatch.setenv("SLACK_ACCESS_TOKEN","s-token")
    sm=SlackModule(http=c(h),channel="C1")
    assert sm.auth_status().ok
    assert sm.send_message("C1",{"text":"hi"})["ok"]
    dm=DiscordModule(http=c(h),webhook_url="https://discord.com/api/webhooks/x/y")
    assert dm.auth_status().ok
    assert dm.send_message("",{"text":"hi"})["id"] == "d1"
    monkeypatch.setenv("LINE_ACCESS_TOKEN","l-token")
    lm=LineModule(http=c(h))
    assert lm.auth_status().ok
    assert lm.send_message("U1",{"text":"hi"}) == {}
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN","w-token")
    wm=WhatsAppModule(http=c(h),phone_number_id="123")
    assert wm.auth_status().ok
    assert wm.send_message("380000000000",{"text":"hi"})["messages"][0]["id"].startswith("wamid")


def test_wordpress_and_devto_native_publish(monkeypatch):
    from orchestrator.platforms.wordpress.module import WordPressModule
    from orchestrator.platforms.devto.module import DevtoModule
    from orchestrator.platforms.base import MediaSpec, PublishMeta
    def h(req):
        if req.url.path.endswith("/users/me"): return httpx.Response(200,json={"name":"wp"},request=req)
        if "/wp-json/wp/v2/posts/" in req.url.path and req.method=="GET": return httpx.Response(200,json={"id":5,"status":"publish","link":"https://wp.example/p/5"},request=req)
        if req.url.path.endswith("/wp-json/wp/v2/posts") and req.method=="POST": return httpx.Response(201,json={"id":5,"link":"https://wp.example/p/5","status":"publish"},request=req)
        if "dev.to/api/users/me" in str(req.url): return httpx.Response(200,json={"username":"dev"},request=req)
        if req.url.path.endswith("/api/articles") and req.method=="POST": return httpx.Response(201,json={"id":6,"url":"https://dev.to/dev/6"},request=req)
        if req.url.path.endswith("/api/articles/6"): return httpx.Response(200,json={"id":6,"url":"https://dev.to/dev/6"},request=req)
        return httpx.Response(200,json={},request=req)
    w=WordPressModule(http=c(h),base_url="https://wp.example",username="u",app_password="p")
    assert w.auth_status().ok
    wr=w.publish(w.prepare(MediaSpec(path="",kind="text")),PublishMeta(title="T",description="B"))
    assert wr.external_id=="5" and w.get_status("5").state=="published"
    monkeypatch.setenv("DEVTO_API_KEY","d")
    d=DevtoModule(http=c(h))
    assert d.auth_status().ok
    dr=d.publish(d.prepare(MediaSpec(path="",kind="text")),PublishMeta(title="T",description="B"))
    assert dr.external_id=="6" and d.get_status("6").state=="published"


def test_lemmy_native_post_status_delete(monkeypatch):
    from orchestrator.platforms.lemmy.module import LemmyModule
    from orchestrator.platforms.base import MediaSpec, PublishMeta
    def h(req):
        if req.method == "POST" and req.url.path.endswith("/user/login"):
            return httpx.Response(200, json={"jwt":"jwt1"}, request=req)
        if req.method == "GET" and req.url.path.endswith("/site"):
            return httpx.Response(200, json={"site":{"name":"demo"}}, request=req)
        if req.method == "POST" and req.url.path.endswith("/post"):
            return httpx.Response(200, json={"post_view":{"post":{"id":7,"ap_id":"https://lemmy.example/post/7"}}}, request=req)
        if req.method == "GET" and req.url.path.endswith("/post"):
            return httpx.Response(200, json={"post_view":{"post":{"id":7,"ap_id":"https://lemmy.example/post/7"}}}, request=req)
        if req.method == "POST" and req.url.path.endswith("/post/delete"):
            return httpx.Response(200, json={"post_view":{"post":{"id":7,"deleted":True}}}, request=req)
        return httpx.Response(200, json={}, request=req)
    monkeypatch.setenv("LEMMY_BASE_URL", "https://lemmy.example")
    monkeypatch.setenv("LEMMY_USERNAME", "u")
    monkeypatch.setenv("LEMMY_PASSWORD", "p")
    monkeypatch.setenv("LEMMY_COMMUNITY_ID", "42")
    m=LemmyModule(http=c(h))
    assert m.auth_status().ok
    r=m.publish(m.prepare(MediaSpec(path="", kind="text")), PublishMeta(title="Hello", description="Body"))
    assert r.external_id == "7"
    assert m.get_status("7").state == "published"
    assert m.delete("7") is True
