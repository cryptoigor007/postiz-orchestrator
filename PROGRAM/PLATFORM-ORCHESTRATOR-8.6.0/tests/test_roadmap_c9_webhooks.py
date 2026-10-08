from __future__ import annotations
from pathlib import Path
from orchestrator.db import Database
from orchestrator.webhook_processor import WebhookEventProcessor


def test_webhook_duplicate_is_idempotent_and_processes(tmp_path):
    db=Database(tmp_path/'w.sqlite')
    payload='{"type":"status","id":"r1","status":"published"}'
    db.execute("INSERT INTO webhook_events(provider,account_id,event_id,payload_hash,signature_valid,received_at,payload_json) VALUES('x','a','e1','h',1,datetime('now'),?)",(payload,))
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,external_id) VALUES('short',1,'x','a','processing','r1')")
    p=WebhookEventProcessor(db)
    r=p.run()
    assert r.processed==1 and r.repaired==1
    assert db.fetchone("SELECT status FROM entity_platform_status WHERE platform='x' AND external_id='r1'")["status"]=='published'
    assert p.run().processed==0


def test_webhook_replay_requeues_event(tmp_path):
    db=Database(tmp_path/'w2.sqlite')
    db.execute("INSERT INTO webhook_events(provider,account_id,event_id,payload_hash,signature_valid,received_at,payload_json,processing_state,processed_at) VALUES('x','a','e1','h',1,datetime('now'),'{}','done',datetime('now'))")
    eid=db.fetchone("SELECT id FROM webhook_events")["id"]
    p=WebhookEventProcessor(db)
    assert p.replay(eid)
    assert db.fetchone("SELECT processing_state,processed_at FROM webhook_events WHERE id=?",(eid,))["processing_state"]=='retry'


def test_webhook_without_external_id_is_retried_not_done(tmp_path):
    db=Database(tmp_path/'w3.sqlite')
    db.execute("INSERT INTO webhook_events(provider,account_id,event_id,payload_hash,signature_valid,received_at,payload_json) VALUES('x','a','e2','h2',1,datetime('now'),?)", ('{"type":"status"}',))
    p=WebhookEventProcessor(db, max_attempts=2)
    r=p.run()
    row=db.fetchone("SELECT processing_state,processed_at,last_error FROM webhook_events WHERE event_id='e2'")
    assert r.processed==0 and r.retried==1
    assert row['processing_state']=='retry' and row['processed_at'] is None
    assert 'missing_external_id' in (row['last_error'] or '') or 'missing external_id' in (row['last_error'] or '')


def test_status_sync_auth_failure_never_creates_missing_streak(tmp_path):
    from orchestrator.db import Database
    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.platforms.base import ModuleError, ModuleErrorCode
    from orchestrator.status_sync import StatusSync
    from datetime import UTC, datetime
    root=Path(__file__).resolve().parents[1]
    db=Database(tmp_path/'ss.sqlite')
    db.ensure_platform_states(['youtube'])
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,external_id,last_error) VALUES('short',1,'youtube','acct','scheduled','ext',NULL)")
    cfg=load_config(root/'config.ci.yaml')
    class Registry:
        def has(self, module_id): return True
        def create(self, *args, **kwargs): raise ModuleError(ModuleErrorCode.AUTH_EXPIRED, 'expired')
    sync=StatusSync(db, FakeClock(datetime(2026,3,10,12,0,tzinfo=UTC)), cfg, registry=Registry())
    sync.sync()
    row=db.fetchone("SELECT status,last_error FROM entity_platform_status WHERE platform='youtube' AND account_id='acct'")
    assert row['status']=='scheduled'
    assert (row['last_error'] or '').startswith('status_sync_error:AUTH_EXPIRED:')
    assert not (row['last_error'] or '').startswith('missing_on_platform:')
