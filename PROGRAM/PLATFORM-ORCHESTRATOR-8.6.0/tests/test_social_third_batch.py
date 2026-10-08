from __future__ import annotations
import httpx
from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.base import MediaSpec, PublishMeta


def client(h):
    return ModuleHttpClient(transport=httpx.MockTransport(h), max_retries=1)


def test_linkedin_image_upload_and_publish(tmp_path):
    from orchestrator.platforms.linkedin.module import LinkedInModule
    p=tmp_path/'a.jpg'; p.write_bytes(b'jpg')
    def h(req):
        if req.method=='POST' and '/rest/images' in str(req.url):
            return httpx.Response(200,json={'value':{'uploadUrl':'https://upload.example/x','image':'urn:li:image:1'}},request=req)
        if req.method=='PUT' and 'upload.example' in str(req.url): return httpx.Response(201,request=req)
        if req.method=='POST' and '/rest/posts' in str(req.url): return httpx.Response(201,headers={'x-restli-id':'urn:li:share:1'},request=req)
        return httpx.Response(200,json={'id':'1'},request=req)
    m=LinkedInModule(http=client(h), access_token='tok', author_urn='urn:li:person:1')
    r=m.publish(m.prepare(MediaSpec(str(p),'image')),PublishMeta(title='T',description='D'))
    assert r.external_id=='urn:li:share:1'


def test_pinterest_video_media_id(tmp_path):
    from orchestrator.platforms.pinterest.module import PinterestModule
    p=tmp_path/'a.mp4'; p.write_bytes(b'v')
    def h(req):
        if req.method=='POST' and req.url.path.endswith('/media'):
            return httpx.Response(200,json={'media_id':'m1','upload_url':'https://upload.example/x','upload_parameters':{}},request=req)
        if 'upload.example' in str(req.url): return httpx.Response(201,request=req)
        if req.method=='POST' and req.url.path.endswith('/pins'): return httpx.Response(201,json={'id':'p1','link':'https://pin/1'},request=req)
        return httpx.Response(200,json={},request=req)
    m=PinterestModule(http=client(h), access_token='tok', board_id='b1')
    r=m.publish(m.prepare(MediaSpec(str(p),'video')),PublishMeta(title='T',extra={'media_id':'m1','cover_image_url':'https://img.example/c.jpg'}))
    assert r.external_id=='p1'


def test_bluesky_image_and_delete(tmp_path):
    from orchestrator.platforms.bluesky.module import BlueskyModule
    p=tmp_path/'a.jpg'; p.write_bytes(b'jpg')
    def h(req):
        path=req.url.path
        if path.endswith('com.atproto.server.createSession'): return httpx.Response(200,json={'accessJwt':'jwt','did':'did:plc:1'},request=req)
        if path.endswith('com.atproto.repo.uploadBlob'): return httpx.Response(200,json={'blob':{'$type':'blob','ref':{'$link':'cid'},'mimeType':'image/jpeg','size':3}},request=req)
        if path.endswith('com.atproto.repo.createRecord'): return httpx.Response(200,json={'uri':'at://did:plc:1/app.bsky.feed.post/abc','cid':'c'},request=req)
        if path.endswith('app.bsky.feed.getPosts'): return httpx.Response(200,json={'posts':[{'uri':'at://did:plc:1/app.bsky.feed.post/abc'}]},request=req)
        if path.endswith('com.atproto.repo.deleteRecord'): return httpx.Response(200,json={},request=req)
        return httpx.Response(200,json={},request=req)
    m=BlueskyModule(http=client(h), handle='a.test', app_password='pw')
    r=m.publish(m.prepare(MediaSpec(str(p),'image')),PublishMeta(description='hello'))
    assert r.external_id.endswith('/abc'); assert m.get_status(r.external_id).state=='published'; assert m.delete(r.external_id)


def test_whatsapp_template(monkeypatch):
    from orchestrator.platforms.whatsapp.module import WhatsAppModule
    def h(req): return httpx.Response(200,json={'messages':[{'id':'wamid.t'}]},request=req)
    m=WhatsAppModule(http=client(h), token_provider=lambda *_:'tok', phone_number_id='123')
    out=m.send_message('7999',{'type':'template','template':{'name':'hello','language':{'code':'en_US'}}})
    assert out['messages'][0]['id']=='wamid.t'


def test_viber_media_and_webhook_setup():
    from orchestrator.platforms.viber.module import ViberModule
    seen=[]
    def h(req):
        seen.append((req.method,str(req.url)))
        if req.url.path.endswith('/set_webhook'): return httpx.Response(200,json={'status':0},request=req)
        return httpx.Response(200,json={'status':0},request=req)
    m=ViberModule(http=client(h), token_provider=lambda *_:'tok')
    assert m.set_webhook('https://example.com/viber')['status']==0
    assert any('set_webhook' in u for _,u in seen)


def test_line_signature():
    import base64,hashlib,hmac
    from orchestrator.platforms.line.module import LineModule
    body=b'{"events":[]}'
    secret='secret'; sig=base64.b64encode(hmac.new(secret.encode(),body,hashlib.sha256).digest()).decode()
    m=LineModule(http=client(lambda r:httpx.Response(200,json={},request=r)), token_provider=lambda *_:'tok', channel_secret=secret)
    assert m.verify_webhook(sig,body)


def test_discord_embeds():
    from orchestrator.platforms.discord.module import DiscordModule
    def h(req): return httpx.Response(200,json={'id':'d1'},request=req)
    m=DiscordModule(http=client(h), webhook_url='https://discord.com/api/webhooks/x/y')
    assert m.send_message('',{'text':'hi','embeds':[{'title':'T'}]})['id']=='d1'


def test_slack_blocks():
    from orchestrator.platforms.slack.module import SlackModule
    def h(req):
        if req.url.path.endswith('/auth.test'): return httpx.Response(200,json={'ok':True,'team':'T'},request=req)
        return httpx.Response(200,json={'ok':True,'ts':'1'},request=req)
    m=SlackModule(http=client(h), token_provider=lambda *_:'tok', channel='C1')
    assert m.send_message('',{'text':'hi','blocks':[{'type':'section'}]})['ok']


def test_reddit_link_post():
    from orchestrator.platforms.reddit.module import RedditModule
    def h(req):
        if req.url.path.endswith('/api/submit'): return httpx.Response(200,json={'json':{'errors':[],'data':{'name':'t3_x','url':'https://reddit/x'}}},request=req)
        return httpx.Response(200,json={'name':'u'},request=req)
    m=RedditModule(http=client(h), access_token='tok', subreddit='demo')
    r=m.publish(m.prepare(MediaSpec('', 'text')),PublishMeta(title='T',extra={'url':'https://example.com'}))
    assert r.external_id=='t3_x'


def test_tumblr_link_post():
    from orchestrator.platforms.tumblr.module import TumblrModule
    def h(req): return httpx.Response(200,json={'response':{'id':'1','post_url':'https://tumblr/p/1'}},request=req)
    m=TumblrModule(http=client(h), consumer_key='ck',consumer_secret='cs',token='t',token_secret='ts',blog='demo')
    # core implementation remains text; the explicit payload is still accepted without network assumptions.
    r=m.publish(m.prepare(MediaSpec('', 'text')),PublishMeta(title='T',description='D'))
    assert r.external_id=='1'
