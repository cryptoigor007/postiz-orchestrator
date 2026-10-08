from __future__ import annotations
import time
from orchestrator.db import Database
from orchestrator.accounts.store import PlatformAccountStore
from orchestrator.connection_control import ConnectionControl
from orchestrator.token_lifecycle import TokenLifecycleStore


class Manifest:
    auth = {"method": "oauth", "strategy": "test"}
class Mod:
    manifest = Manifest()
class Registry:
    def has(self, p): return p == "test"
    def create(self, p, **kwargs): return Mod()


def test_connection_checklist_and_disconnect(tmp_path):
    db=Database(tmp_path/"c.sqlite")
    accounts=PlatformAccountStore(db)
    accounts.upsert(platform="test", external_account_id="a1", account_id="a1", enabled=True, connection_state="CONNECTED")
    tokens=TokenLifecycleStore(tmp_path/"tokens", db=db)
    tokens.rotate("test", "a1", access_token="tok", expires_at=time.time()+3600)
    cc=ConnectionControl(db, Registry(), tokens, accounts)
    c=cc.checklist("test", "a1")
    assert c.ready is True
    assert cc.disconnect("a1") is True
    assert cc.checklist("test", "a1").ready is False
