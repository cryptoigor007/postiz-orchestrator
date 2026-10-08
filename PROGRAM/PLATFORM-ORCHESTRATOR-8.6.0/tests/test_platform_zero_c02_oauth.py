"""platform-zero COMMIT 2: oauth_sessions + OAuth start/callback/PKCE."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.oauth.manager import (  # noqa: E402
    GOOGLE_YOUTUBE,
    OAuthManager,
    OAuthProviderConfig,
    OAuthTokenResult,
)
from orchestrator.oauth.sessions import (  # noqa: E402
    OAuthSessionStore,
    hash_state,
    new_pkce_pair,
    new_state,
)
from orchestrator.platforms.base import ModuleError, ModuleErrorCode  # noqa: E402


class _MemDB:
    """Minimal SQLite wrapper matching Database execute/fetchone."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE oauth_sessions (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                code_verifier TEXT NOT NULL,
                account_hint TEXT DEFAULT '',
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                consumed_at REAL,
                redirect_uri TEXT DEFAULT ''
            );
        """)

    def close(self):
        if getattr(self, "conn", None) is not None:
            self.conn.close()
            self.conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def execute(self, sql, params=()):
        self.conn.execute(sql, params)
        self.conn.commit()

    def fetchone(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def fetchall(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def test_pkce_pair_shape():
    v, c = new_pkce_pair()
    assert len(v) >= 43
    assert len(c) >= 40
    assert v != c


def test_hash_state_stable():
    assert hash_state("abc") == hash_state("abc")
    assert hash_state("a") != hash_state("b")


def test_session_create_and_lookup():
    db = _MemDB()
    store = OAuthSessionStore(db)
    state = new_state()
    sess = store.create(
        provider="youtube",
        code_verifier="ver",
        state=state,
        redirect_uri="https://orch.example/oauth/callback/youtube",
        account_hint="ch1",
    )
    assert sess.id
    assert not sess.consumed
    assert not sess.expired
    found = store.get_by_state(state)
    assert found is not None
    assert found.id == sess.id
    assert found.account_hint == "ch1"
    assert store.get_by_state("nope") is None


def test_session_consume_and_expiry():
    db = _MemDB()
    store = OAuthSessionStore(db)
    state = new_state()
    sess = store.create(
        provider="youtube", code_verifier="v", state=state,
        redirect_uri="https://x/cb", ttl_sec=0.01,
    )
    time.sleep(0.02)
    found = store.get_by_state(state)
    assert found is not None
    assert found.expired
    store.mark_consumed(sess.id)
    again = store.get(sess.id)
    assert again is not None and again.consumed


def test_oauth_start_builds_url():
    db = _MemDB()
    cfg = OAuthProviderConfig(
        provider="youtube",
        client_id="CID",
        client_secret="SEC",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
        extra_auth_params={"access_type": "offline"},
        use_pkce=True,
    )
    mgr = OAuthManager(
        public_base_url="https://orch.example",
        session_store=OAuthSessionStore(db),
        providers={"youtube": cfg},
    )
    start = mgr.start("youtube", account_hint="main")
    assert "accounts.google.com" in start.authorize_url
    assert "code_challenge=" in start.authorize_url
    assert "code_challenge_method=S256" in start.authorize_url
    assert "state=" in start.authorize_url
    assert "client_id=CID" in start.authorize_url
    assert start.session_id


def test_oauth_start_no_client_id_raises():
    db = _MemDB()
    cfg = OAuthProviderConfig(
        provider="youtube", client_id="", client_secret="",
        authorize_url="https://x/auth", token_url="https://x/token",
    )
    mgr = OAuthManager(
        public_base_url="https://orch.example",
        session_store=OAuthSessionStore(db),
        providers={"youtube": cfg},
    )
    with pytest.raises(ModuleError) as ei:
        mgr.start("youtube")
    assert ei.value.code == ModuleErrorCode.AUTH_REQUIRED


def test_callback_unknown_state():
    db = _MemDB()
    cfg = OAuthProviderConfig(
        provider="youtube", client_id="C", client_secret="S",
        authorize_url="https://x/a", token_url="https://x/t",
    )
    mgr = OAuthManager(
        public_base_url="https://orch.example",
        session_store=OAuthSessionStore(db),
        providers={"youtube": cfg},
    )
    with pytest.raises(ModuleError) as ei:
        mgr.handle_callback("youtube", code="code", state="unknown")
    assert ei.value.code == ModuleErrorCode.AUTH_REQUIRED


def test_callback_success_with_mock_http(tmp_path: Path):
    import httpx
    from orchestrator.http_client import ModuleHttpClient

    class _T(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "access_token": "AT",
                "refresh_token": "RT",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "yt",
            })

    db = _MemDB()
    cfg = OAuthProviderConfig(
        provider="youtube", client_id="C", client_secret="S",
        authorize_url="https://x/a", token_url="https://oauth2.googleapis.com/token",
        use_pkce=True,
    )
    saved = {}

    def saver(provider, result, hint):
        saved["provider"] = provider
        saved["token"] = result.access_token
        saved["hint"] = hint

    http = ModuleHttpClient(
        platform="oauth", module_version="0.1.0",
        transport=_T(), max_retries=1,
    )
    mgr = OAuthManager(
        public_base_url="https://orch.example",
        session_store=OAuthSessionStore(db),
        providers={"youtube": cfg},
        http=http,
        token_saver=saver,
    )
    start = mgr.start("youtube", account_hint="hint1")
    # extract state from URL
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(start.authorize_url).query)
    state = qs["state"][0]
    result = mgr.handle_callback("youtube", code="AUTHCODE", state=state)
    assert result.access_token == "AT"
    assert result.refresh_token == "RT"
    assert saved["token"] == "AT"
    assert saved["hint"] == "hint1"
    # replay must fail
    with pytest.raises(ModuleError):
        mgr.handle_callback("youtube", code="AUTHCODE", state=state)


def test_google_youtube_default_scopes():
    assert any("youtube.upload" in s for s in GOOGLE_YOUTUBE.scopes)
