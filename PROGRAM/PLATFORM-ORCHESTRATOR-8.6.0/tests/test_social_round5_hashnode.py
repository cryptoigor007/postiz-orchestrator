from __future__ import annotations
import httpx
from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.base import MediaSpec, PublishMeta


def client(handler):
    return ModuleHttpClient(transport=httpx.MockTransport(handler), max_retries=1)


def test_hashnode_publish_update_delete_and_inventory():
    from orchestrator.platforms.hashnode.module import HashnodeModule
    calls=[]
    def h(req):
        calls.append(req)
        import json
        body=json.loads(req.content)
        q=body.get('query','')
        if 'publishPost(' in q:
            return httpx.Response(200, json={'data': {'publishPost': {'post': {'id':'p1','slug':'hello','url':'https://hashnode.dev/hello'}}}}, request=req)
        if 'updatePost(' in q:
            return httpx.Response(200, json={'data': {'updatePost': {'post': {'id':'p1'}}}}, request=req)
        if 'removePost(' in q:
            return httpx.Response(200, json={'data': {'removePost': {'post': {'id':'p1'}}}}, request=req)
        if 'publication(id:' in q:
            return httpx.Response(200, json={'data': {'publication': {'posts': {'edges':[{'cursor':'c1','node':{'id':'p1','title':'T','url':'https://hashnode.dev/t','brief':'B','publishedAt':'2026-10-01T10:00:00Z'}}], 'pageInfo': {'hasNextPage': False,'endCursor':'c1'}}}}}, request=req)
        if 'post(id:' in q:
            return httpx.Response(200, json={'data': {'post': {'id':'p1','title':'T','url':'https://hashnode.dev/t','publishedAt':'2026-10-01T10:00:00Z','preferences':{'isDelisted':False}}}}, request=req)
        if ' me ' in q or 'me {' in q:
            return httpx.Response(200, json={'data': {'me': {'id':'u1','username':'demo','publications': {'edges':[{'node':{'id':'pub1','title':'Demo','url':'https://demo.hashnode.dev'}}]}}}}, request=req)
        return httpx.Response(200, json={'data': {}}, request=req)
    m=HashnodeModule(http=client(h), token='tok', publication_id='pub1')
    r=m.publish(m.prepare(MediaSpec('', 'text')), PublishMeta(title='T', description='Body'))
    assert r.external_id=='p1'
    assert m.update_metadata('p1', PublishMeta(title='T2')) is True
    assert m.get_status('p1').state=='published'
    assert m.list_remote_items(limit=10).items[0].external_id=='p1'
    assert m.delete('p1') is True
    assert m.manifest.capabilities['update_metadata'] is True
