from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.auth_tokens import get_access_token
from orchestrator.db import Database, SCHEMA_VERSION
from orchestrator.oauth.manager import FACEBOOK, INSTAGRAM, THREADS, meta_graph_version
from orchestrator.oauth.sessions import OAuthSessionStore, new_state
from orchestrator.provider_supervisor import ProviderSupervisor
from orchestrator.platforms import default_registry


def test_schema_foundation_tables_and_version(tmp_path):
    db = Database(tmp_path / "x.sqlite")
    assert int(db.fetchone("SELECT value FROM system_state WHERE key='schema_version'")["value"]) == SCHEMA_VERSION
    names = {r["name"] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"provider_health", "provider_access", "publish_attempts", "outbox_events", "webhook_events", "durable_jobs", "distribution_targets", "media_artifacts", "consistency_runs"} <= names
    assert "claimed_at" in {r["name"] for r in db.fetchall("PRAGMA table_info(oauth_sessions)")}


def test_auth_tokens_uses_configured_broker(monkeypatch):
    calls = {}
    class FakeBroker:
        def __init__(self, url, secret):
            calls["init"] = (url, secret)
        def get(self, platform, integration_id=None):
            calls["get"] = (platform, integration_id)
            return {"token": "BROKER_TOKEN"}
    monkeypatch.setenv("TOKEN_BROKER_URL", "http://broker")
    monkeypatch.setenv("TOKEN_BROKER_SECRET", "secret")
    import orchestrator.engines.token_broker_client as mod
    monkeypatch.setattr(mod, "TokenBrokerClient", FakeBroker)
    assert get_access_token("youtube", "acc1") == "BROKER_TOKEN"
    assert calls["init"] == ("http://broker", "secret")
    assert calls["get"] == ("youtube", "acc1")


def test_auth_tokens_prefers_account_file(monkeypatch, tmp_path):
    monkeypatch.delenv("TOKEN_BROKER_URL", raising=False)
    monkeypatch.setenv("TOKENS_DIR", str(tmp_path))
    (tmp_path / "instagram.json").write_text(json.dumps({"access_token": "GLOBAL"}))
    (tmp_path / "instagram__a1.json").write_text(json.dumps({"access_token": "ACCOUNT"}))
    assert get_access_token("instagram", "a1") == "ACCOUNT"


def test_oauth_session_claim_is_one_shot(tmp_path):
    db = Database(tmp_path / "oauth.sqlite")
    store = OAuthSessionStore(db)
    state = new_state()
    sess = store.create(provider="threads", code_verifier="v", state=state, redirect_uri="http://localhost/cb")
    assert store.claim(sess.id) is True
    assert store.claim(sess.id) is False
    store.release_claim(sess.id)
    assert store.claim(sess.id) is True
    store.mark_consumed(sess.id)
    assert store.claim(sess.id) is False


def test_meta_provider_configs_are_explicit():
    assert meta_graph_version() == "v26.0"
    assert "pages_manage_posts" in FACEBOOK.scopes
    assert "instagram_content_publish" in INSTAGRAM.scopes
    assert "threads_content_publish" in THREADS.scopes


def test_planned_provider_modules_are_registered_but_honest():
    reg = default_registry()
    signal = reg.create("signal")
    assert signal.manifest.capability("publish") is False
    assert signal.manifest.publish_mode == "unsupported"
    snapchat = reg.create("snapchat")
    assert snapchat.manifest.capability("publish") is True
    assert snapchat.manifest.publish_mode == "direct"

    moltbook = reg.create("moltbook")
    assert moltbook.manifest.capability("publish") is True
    assert moltbook.manifest.publish_mode == "direct"
    nostr = reg.create("nostr")
    assert nostr.manifest.capability("publish") is True
    assert nostr.manifest.publish_mode == "direct"
    wechat = reg.create("wechat")
    assert wechat.manifest.capability("publish") is True
    assert wechat.manifest.publish_mode == "direct"

    for mid in ("linkedin", "pinterest", "tumblr"):
        assert reg.has(mid)
        m = reg.create(mid)
        assert m.manifest.capability("publish") is True
        assert m.manifest.publish_mode == "direct"

    for mid in ("whatsapp", "viber"):
        assert reg.has(mid)
        m = reg.create(mid)
        assert m.manifest.capability("publish") is False
        assert m.manifest.publish_mode == "unsupported"
        assert m.manifest.capability("messages") is True


def test_provider_supervisor_isolates_account_failure(tmp_path):
    db = Database(tmp_path / "health.sqlite")
    sup = ProviderSupervisor(db, failure_threshold=2, cooldown_sec=60)
    sup.record_failure("tiktok", "a1", "429")
    assert sup.allow("tiktok", "a1") is True
    sup.record_failure("tiktok", "a1", "429")
    assert sup.allow("tiktok", "a1") is False
    assert sup.allow("youtube", "a1") is True
    row = db.fetchone("SELECT state, consecutive_failures FROM provider_health WHERE platform='tiktok' AND account_id='a1'")
    assert row["state"] == "open"
    assert int(row["consecutive_failures"]) == 2


def test_provider_supervisor_restores_persisted_state(tmp_path):
    db = Database(tmp_path / "health-reload.sqlite")
    sup1 = ProviderSupervisor(db, failure_threshold=1, cooldown_sec=60)
    sup1.record_failure("instagram", "a1", "timeout")
    assert sup1.allow("instagram", "a1") is False

    sup2 = ProviderSupervisor(db, failure_threshold=1, cooldown_sec=60)
    assert sup2.allow("instagram", "a1") is False
    snap = sup2.snapshot()
    assert snap["instagram::a1"]["state"] == "open"
    assert snap["instagram::a1"]["last_error"] == "timeout"


def test_provider_access_store_roundtrip(tmp_path):
    from orchestrator.provider_access import ProviderAccessSnapshot, ProviderAccessStore
    db = Database(tmp_path / "access.sqlite")
    store = ProviderAccessStore(db)
    snap = ProviderAccessSnapshot(provider="instagram", account_id="a1", token_ok=True, scopes_ok=True, state="CONNECTED", details="ok")
    store.upsert(snap)
    got = store.get("instagram", "a1")
    assert got is not None
    assert got.token_ok is True
    assert got.scopes_ok is True
    assert got.state == "CONNECTED"


def test_api_version_registry_rejects_past_sunset():
    from datetime import date
    from orchestrator.api_versions import ApiVersionRecord, validate_no_sunset
    records = {"x": ApiVersionRecord("x", "v1", sunset_at=date(2026, 1, 1))}
    assert validate_no_sunset(records, today=date(2026, 10, 1))


def test_account_scoped_token_does_not_fallback_to_shared_file(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setenv("TOKENS_DIR", str(tmp_path))
    (tmp_path / "instagram.json").write_text('{"access_token":"SHARED"}', encoding="utf-8")
    assert get_access_token("instagram", "account-A") == ""

def test_shared_token_fallback_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENS_DIR", str(tmp_path))
    monkeypatch.setenv("TOKEN_ALLOW_SHARED_FALLBACK", "1")
    (tmp_path / "instagram.json").write_text('{"access_token":"SHARED"}', encoding="utf-8")
    assert get_access_token("instagram", "account-A") == "SHARED"


def test_durable_job_enqueue_is_idempotent(tmp_path):
    from orchestrator.outbox import DurableJobStore
    db = Database(tmp_path / "jobs.sqlite")
    jobs = DurableJobStore(db)
    jid = jobs.enqueue("publish.completed", {"platform": "youtube"}, provider="youtube", account_id="a1", job_id="outbox:1")
    same = jobs.enqueue("publish.completed", {"platform": "youtube", "duplicate": True}, provider="youtube", account_id="a1", job_id="outbox:1")
    assert same == jid
    rows = db.fetchall("SELECT id, payload_json FROM durable_jobs WHERE id=?", (jid,))
    assert len(rows) == 1
    assert "duplicate" not in rows[0]["payload_json"]
