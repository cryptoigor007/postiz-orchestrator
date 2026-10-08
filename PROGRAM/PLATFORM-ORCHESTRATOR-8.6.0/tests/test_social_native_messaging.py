from __future__ import annotations
import httpx
from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.whatsapp.module import WhatsAppModule
from orchestrator.platforms.viber.module import ViberModule
from orchestrator.platforms.discord.module import DiscordModule
from orchestrator.platforms.line.module import LineModule
from orchestrator.platforms.mastodon.module import MastodonModule


def client_for(handler):
    return ModuleHttpClient(transport=httpx.MockTransport(handler), max_retries=1)


def test_whatsapp_send_text(monkeypatch):
    seen={}
    def h(req): seen['req']=req; return httpx.Response(200,json={'messages':[{'id':'wamid.1'}]},request=req)
    monkeypatch.setenv('WHATSAPP_PHONE_NUMBER_ID','123')
    m=WhatsAppModule(token_provider=lambda *_:'tok', http=client_for(h))
    out=m.send_message('7999', {'text':'hi'})
    assert out['messages'][0]['id']=='wamid.1'; assert b'whatsapp' in seen['req'].content


def test_viber_send_text(monkeypatch):
    seen={}
    def h(req): seen['req']=req; return httpx.Response(200,json={'status':0},request=req)
    m=ViberModule(token_provider=lambda *_:'tok', http=client_for(h))
    out=m.send_message('user1', {'text':'hi'})
    assert out['status']==0; assert seen['req'].headers['X-Viber-Auth-Token']=='tok'


def test_discord_webhook():
    def h(req): return httpx.Response(204,request=req)
    m=DiscordModule(http=client_for(h))
    assert m.send_message('https://discord.com/api/webhooks/x/y', {'text':'hi'})['ok'] is True


def test_line_push(monkeypatch):
    def h(req): return httpx.Response(200,json={},request=req)
    m=LineModule(token_provider=lambda *_:'tok', http=client_for(h))
    assert m.send_message('U1', {'text':'hi'}) == {}


def test_mastodon_publish_and_status(monkeypatch):
    calls=[]
    def h(req):
        calls.append((req.method,req.url))
        if req.method=='POST': return httpx.Response(200,json={'id':'1','url':'https://m/@a/1'},request=req)
        return httpx.Response(200,json={'id':'1','url':'https://m/@a/1'},request=req)
    monkeypatch.setenv('MASTODON_BASE_URL','https://m.example')
    m=MastodonModule(token_provider=lambda *_:'tok', http=client_for(h))
    from orchestrator.platforms.base import MediaSpec, PublishMeta
    r=m.publish(m.prepare(MediaSpec(path='',kind='text')), PublishMeta(title='hi'))
    assert r.external_id=='1'
    assert m.get_status('1').state=='published'
