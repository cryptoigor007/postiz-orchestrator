from __future__ import annotations
import httpx
from orchestrator.db import Database
from orchestrator.http_client import ModuleHttpClient
from orchestrator.provider_supervisor import ProviderSupervisor


def test_eps_supports_two_accounts(tmp_path):
    db=Database(tmp_path/'a.sqlite')
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES(?,?,?,?,?)",('short',1,'instagram','a','ready'))
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES(?,?,?,?,?)",('short',1,'instagram','b','ready'))
    assert len(db.fetchall("SELECT * FROM entity_platform_status WHERE entity_type='short' AND entity_id=1 AND platform='instagram'"))==2


def test_non_idempotent_post_429_is_not_retried():
    calls=[]
    def h(req):
        calls.append(1)
        return httpx.Response(429, headers={'Retry-After':'0'}, request=req)
    c=ModuleHttpClient(transport=httpx.MockTransport(h), max_retries=4)
    r=c.request('POST','https://example.test/create',json={'x':1},idempotent=False)
    assert r.status_code==429 and len(calls)==1


def test_provider_supervisor_isolated_by_account():
    s=ProviderSupervisor()
    for _ in range(5): s.record_failure('instagram','a','boom')
    assert not s.allow('instagram','a')
    assert s.allow('instagram','b')


def test_publisher_account_override_isolated(tmp_path):
    from orchestrator.config import load_config
    from orchestrator.clock import FakeClock
    from orchestrator.safety import SafetyChecker
    from orchestrator.publisher import Publisher
    from datetime import UTC, datetime
    db=Database(tmp_path/"p.sqlite"); cfg=load_config("config.ci.yaml"); clock=FakeClock(datetime(2026,10,1,12,0,tzinfo=UTC))
    class Reg:
        def has(self, module_id): return True
        def create(self, module_id, **deps):
            class M:
                def prepare(self, media): return media
                def publish(self, media, meta):
                    from orchestrator.platforms.base import PublishResult
                    return PublishResult(external_id="dry", state="published")
            return M()
    pub=Publisher(db,cfg,SafetyChecker(db,cfg,clock),clock,dry_run=True,module_registry=Reg())
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES(?,?,?,?,?)",("short",1,"youtube","a","ready"))
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES(?,?,?,?,?)",("short",1,"youtube","b","ready"))
    assert pub._already_exists("short",1,"youtube","a") is None
    assert pub._reserve_publish("short",1,"youtube","a") is True
    assert pub._reserve_publish("short",1,"youtube","b") is True
