from __future__ import annotations
import time
from orchestrator.db import Database
from orchestrator.token_lifecycle import TokenLifecycleStore
from orchestrator.auth_tokens import get_access_token


def test_token_rotation_is_atomic_and_account_scoped(tmp_path, monkeypatch):
    db = Database(tmp_path / "t.sqlite")
    db.execute("INSERT INTO platform_accounts(id,platform,account_id) VALUES('a1','instagram','a1')") if False else None
    store = TokenLifecycleStore(tmp_path / "tokens", db=db)
    rec = store.rotate("instagram", "a1", access_token="A", refresh_token="R", expires_at=time.time()+3600)
    assert rec.version == 1
    assert store.load("instagram", "a1").access_token == "A"
    rec2 = store.rotate("instagram", "a1", access_token="B", refresh_token="R2", expires_at=time.time()+3600)
    assert rec2.version == 2
    monkeypatch.setenv("TOKENS_DIR", str(tmp_path / "tokens"))
    assert get_access_token("instagram", "a1") == "B"


def test_revoked_or_quarantined_tokens_are_not_resolved(tmp_path, monkeypatch):
    store = TokenLifecycleStore(tmp_path / "tokens")
    store.rotate("x", "a", access_token="tok", expires_at=time.time()+3600)
    assert store.revoke("x", "a") is True
    monkeypatch.setenv("TOKENS_DIR", str(tmp_path / "tokens"))
    assert get_access_token("x", "a") == ""
    store.rotate("x", "a", access_token="tok2", expires_at=time.time()+3600)
    store.quarantine("x", "a", reason="auth anomaly")
    assert get_access_token("x", "a") == ""
