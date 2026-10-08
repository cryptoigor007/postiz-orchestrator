"""Necessary residual N1–N6 / N13 tests."""
from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from orchestrator.oauth.manager import OAuthManager, OAuthProviderConfig


ROOT = Path(__file__).resolve().parents[1]


def test_n1_oauth_callback_public_no_telegram_auth():
    """OAuth callback must not require Telegram initData (handled before _auth)."""
    src = (ROOT / "src/orchestrator/webapp_api.py").read_text(encoding="utf-8")
    assert "_oauth_public" in src
    assert "route_early.startswith(\"oauth/callback/\")" in src or "oauth/callback/" in src
    # public branch returns before unauthorized
    idx_pub = src.find("_oauth_public")
    idx_auth = src.find("auth = self._auth", idx_pub)
    assert idx_pub > 0 and idx_auth > idx_pub


def test_n5_vk_schedule_publish_false():
    text = (ROOT / "src/orchestrator/platforms/vk/manifest.yaml").read_text(encoding="utf-8")
    assert "schedule_publish: false" in text


def test_n6_get_access_token_from_file(tmp_path, monkeypatch):
    from orchestrator.auth_tokens import get_access_token
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "tokens"
    d.mkdir()
    (d / "youtube.json").write_text(
        '{"access_token": "tok_abc", "expires_at": 9999999999}', encoding="utf-8"
    )
    assert get_access_token("youtube") == "tok_abc"
    assert get_access_token("missing") == ""




def test_n6_account_specific_token_is_used_when_shared_missing(tmp_path, monkeypatch):
    from orchestrator.auth_tokens import get_access_token
    monkeypatch.setenv("TOKENS_DIR", str(tmp_path / "tokens"))
    root = tmp_path / "tokens"
    root.mkdir()
    (root / "youtube__acct.json").write_text('{"access_token":"specific"}', encoding="utf-8")
    assert get_access_token("youtube", account_id="acct") == "specific"

def test_n13_threads_get_status_not_always_published():
    import httpx
    from orchestrator.http_client import ModuleHttpClient
    from orchestrator.platforms.threads.module import ThreadsModule

    # dry_run
    m = ThreadsModule(dry_run=True)
    st = m.get_status("x")
    assert st.state == "published"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"message": "mock outage"}})

    http = ModuleHttpClient(platform="threads", transport=httpx.MockTransport(handler), max_retries=1)
    m2 = ThreadsModule(access_token="token", http=http, dry_run=False)
    st2 = m2.get_status("x")
    assert st2.state == "unknown"
    assert st2.error


def test_n3_local_schedule_due_method_exists():
    from orchestrator.runner import Runner
    assert hasattr(Runner, "_cycle_local_schedule_due")


def test_oauth_callback_uri():
    mgr = OAuthManager(public_base_url="https://ex.com", session_store=None, providers={})
    assert mgr.callback_uri("youtube").endswith("/webapp/api/oauth/callback/youtube")


def test_n1_webapp_callback_bypasses_telegram_auth(monkeypatch, tmp_path):
    from orchestrator.config import load_config
    from orchestrator.db import Database
    from orchestrator.webapp_api import WebAppAPI

    db = Database(tmp_path / "oauth.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    api = WebAppAPI({"db": db, "cfg": cfg})
    seen = {}

    def fake_callback(provider, params):
        seen["provider"] = provider
        seen["params"] = params
        return {"ok": True}

    monkeypatch.setattr(api, "_oauth_callback", fake_callback)
    code, payload, ctype = api.handle(
        "GET",
        "/webapp/api/oauth/callback/youtube?code=abc&state=state123",
        {},
        b"",
    )
    assert code == 200
    assert payload == {"ok": True}
    assert ctype == "application/json"
    assert seen == {"provider": "youtube", "params": {"code": "abc", "state": "state123"}}


def test_n2_token_save_failure_does_not_enable_account(tmp_path):
    import sqlite3
    import pytest
    from orchestrator.oauth.manager import OAuthManager
    from orchestrator.oauth.sessions import OAuthSessionStore
    from orchestrator.http_client import ModuleHttpClient
    import httpx

    class DB:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            self.conn.executescript("""
            CREATE TABLE oauth_sessions (id TEXT PRIMARY KEY, provider TEXT NOT NULL,
                state_hash TEXT NOT NULL, code_verifier TEXT NOT NULL, account_hint TEXT DEFAULT '',
                created_at REAL NOT NULL, expires_at REAL NOT NULL, consumed_at REAL, redirect_uri TEXT DEFAULT '');
            """)

        def close(self):
            if getattr(self, "conn", None) is not None:
                self.conn.close()
                self.conn = None

        def __del__(self):
            try:
                self.close()
            except Exception:
                return

        def execute(self, sql, params=()):
            self.conn.execute(sql, params); self.conn.commit()

        def fetchone(self, sql, params=()):
            row = self.conn.execute(sql, params).fetchone()
            return dict(row) if row else None

        def fetchall(self, sql, params=()):
            return [dict(x) for x in self.conn.execute(sql, params).fetchall()]

    class Transport(httpx.BaseTransport):
        def handle_request(self, request):
            return httpx.Response(200, json={"access_token": "AT", "expires_in": 3600})

    db = DB()
    cfg = OAuthProviderConfig(
        provider="youtube", client_id="C", client_secret="S",
        authorize_url="https://x/auth", token_url="https://x/token",
    )
    enabled_calls = []

    class Accounts:
        def upsert(self, **kwargs):
            enabled_calls.append(kwargs)

    def failing_saver(*_args):
        raise OSError("disk full")

    mgr = OAuthManager(
        public_base_url="https://orch.example",
        session_store=OAuthSessionStore(db),
        providers={"youtube": cfg},
        http=ModuleHttpClient(platform="oauth", module_version="1", transport=Transport()),
        token_saver=failing_saver,
        account_store=Accounts(),
    )
    start = mgr.start("youtube", account_hint="main")
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(start.authorize_url).query)["state"][0]
    with pytest.raises(Exception):
        mgr.handle_callback("youtube", code="CODE", state=state)
    assert enabled_calls == []
    sess = db.fetchone("SELECT consumed_at FROM oauth_sessions")
    assert sess["consumed_at"] is None
    db.close()


def test_n2_token_store_sets_secure_dir_and_file(tmp_path):
    import stat
    from orchestrator.platforms.token_store import OAuthTokenStore, TokenData
    path = tmp_path / "tokens" / "youtube.json"
    OAuthTokenStore("youtube", path).save(TokenData(access_token="tok", expires_at=9999999999))
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert path.read_text(encoding="utf-8").find('"access_token": "tok"') >= 0


def test_n3_local_schedule_due_functionally_publishes(tmp_path):
    from unittest.mock import Mock
    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.db import Database
    from orchestrator.runner import Runner
    from orchestrator.scheduler_recovery import SchedulerRecovery

    db = Database(tmp_path / "due.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    clock = FakeClock(datetime(2026, 10, 1, 12, 0, tzinfo=UTC))
    scheduled_for = (clock.now() - datetime.resolution).isoformat()
    db.execute(
        "INSERT INTO shorts (source, folder_path, title_text, video_path, created_at) "
        "VALUES ('x','/due','Due','/due.mp4',?)", (clock.now().isoformat(),)
    )
    sid = db.fetchone("SELECT id FROM shorts WHERE folder_path='/due'")["id"]
    db.execute(
        "INSERT INTO content_revisions "
        "(id, entity_type, entity_id, revision_hash, content_json, media_path, created_at) "
        "VALUES ('rev-due', 'short', ?, 'hash-due', ?, '/due.mp4', ?)",
        (sid, json.dumps({"title": "Due", "content_kind": "video_native"}), clock.now().isoformat()),
    )
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, account_id, status, external_id, publish_mode, scheduled_for) "
        "VALUES ('short', ?, 'youtube', '', 'scheduled', 'local-youtube-short-due', 'local_schedule', ?)",
        (sid, scheduled_for),
    )
    db.execute(
        "INSERT INTO distribution_targets "
        "(id, entity_type, entity_id, platform, account_id, revision_hash, scheduled_for, publish_mode, status, created_at, updated_at) "
        "VALUES ('target-due', 'short', ?, 'youtube', '', 'hash-due', ?, 'local_schedule', 'queued', ?, ?)",
        (sid, scheduled_for, clock.now().isoformat(), clock.now().isoformat()),
    )
    pub = Mock()
    runner = Runner.__new__(Runner)
    runner.comps = {
        "db": db,
        "cfg": cfg,
        "clock": clock,
        "publisher": pub,
        "scheduler_recovery": SchedulerRecovery(db, clock),
    }
    runner._cycle_local_schedule_due()
    pub.publish.assert_called_once()
    args = pub.publish.call_args.args
    assert args[0:3] == ("short", sid, "youtube")
    assert args[-1] is None
    row = db.fetchone(
        "SELECT status, external_id FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=? AND platform='youtube'",
        (sid,),
    )
    assert row["status"] == "ready"
    assert row["external_id"] is None


def test_n4_retryable_publish_failure_clears_lease(tmp_path):
    from unittest.mock import Mock
    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.db import Database
    from orchestrator.publisher import Publisher
    from orchestrator.safety import SafetyChecker
    from orchestrator.platforms.base import ModuleError, ModuleErrorCode, PublishResult

    db = Database(tmp_path / "publish.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    clock = FakeClock(datetime(2026, 10, 1, 12, 0, tzinfo=UTC))
    safety = SafetyChecker(db, cfg, clock)

    class Mod:
        manifest = type("M", (), {"core_min": ""})()
        def prepare(self, media): return media
        def publish(self, media, meta):
            raise ModuleError(ModuleErrorCode.TRANSIENT, "temporary", retryable=True)

    class Reg:
        def has(self, module_id): return True
        def create(self, module_id, **deps): return Mod()

    p = Publisher(db, cfg, safety, clock, dry_run=False, module_registry=Reg())
    with pytest.raises(ModuleError):
        p.publish("short", 1, "youtube", None, {"title": "x"}, None)
    row = db.fetchone("SELECT status, last_error, lease_until, next_retry_at FROM entity_platform_status WHERE entity_type='short' AND entity_id=1 AND platform='youtube'")
    assert row["status"] == "ready"
    assert "temporary" in row["last_error"]
    assert row["lease_until"] is None
    assert row["next_retry_at"]


def test_n9_config_rejects_duplicate_yaml_keys(tmp_path):
    import pytest
    from orchestrator.config import ConfigurationError, load_config
    path = tmp_path / "dup.yaml"
    path.write_text((ROOT / "config.ci.yaml").read_text(encoding="utf-8") + "\nengines:\n  youtube: module:youtube\n  youtube: module:telegram\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(path)


def test_n9_manifest_rejects_duplicate_yaml_keys(tmp_path):
    import pytest
    from orchestrator.platforms.manifest import ManifestError, load_manifest
    src = (ROOT / "src/orchestrator/platforms/vk/manifest.yaml").read_text(encoding="utf-8")
    path = tmp_path / "manifest.yaml"
    path.write_text(src + "\nid: duplicate\n", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)


def test_n15_fresh_database_verifies_eps_schema(tmp_path):
    from orchestrator.db import Database, verify_eps_schema
    db = Database(tmp_path / "schema.sqlite")
    verify_eps_schema(db)


def test_n15_missing_critical_column_fails_closed(tmp_path):
    import sqlite3
    import pytest
    from orchestrator.db import Database

    path = tmp_path / "broken.sqlite"
    Database(path)
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE entity_platform_status")
    conn.execute(
        "CREATE VIEW entity_platform_status AS "
        "SELECT NULL AS entity_type, NULL AS entity_id, NULL AS platform, "
        "NULL AS status, NULL AS legacy_post_id, NULL AS legacy_scheduled_for, "
        "NULL AS published_at, NULL AS release_url, NULL AS link_updated_at, "
        "NULL AS last_error, NULL AS deleted_at, NULL AS deleted_reason, NULL AS cascade_from, "
        "NULL AS external_id, NULL AS external_sub_id, NULL AS external_url, "
        "NULL AS scheduled_for, NULL AS publish_mode, NULL AS source, NULL AS privacy, "
        "NULL AS claims_state, NULL AS claims_checked_at, NULL AS lock_owner, "
        "NULL AS lease_until, NULL AS attempt, NULL AS next_retry_at, "
        "NULL AS last_status_sync_at, NULL AS module_version"
    )
    conn.execute("UPDATE system_state SET value='19' WHERE key='schema_version'")
    conn.commit()
    conn.close()

    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        Database(path)
    from contextlib import closing
    with closing(sqlite3.connect(path)) as raw_conn:
        raw = raw_conn.execute(
            "SELECT value FROM system_state WHERE key='schema_version'"
        ).fetchone()[0]
    assert raw == '19'


def test_n10_oauth_handlers_are_extracted():
    from orchestrator.oauth import web
    from orchestrator.webapp_api import WebAppAPI

    assert callable(web.start)
    assert callable(web.callback)
    source = (ROOT / "src/orchestrator/webapp_api.py").read_text(encoding="utf-8")
    assert "def _oauth_start" in source
    assert "from .oauth.web import start" in source
    assert "from .oauth.web import callback" in source
