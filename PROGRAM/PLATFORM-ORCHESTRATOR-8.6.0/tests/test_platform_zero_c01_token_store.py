"""platform-zero COMMIT 1: fail-closed token store + broker without platform DB."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrator.platforms.base import ModuleError, ModuleErrorCode  # noqa: E402
from orchestrator.platforms.token_store import (  # noqa: E402
    OAuthTokenStore,
    TokenData,
    make_meta_token_store,
    make_tiktok_token_store,
)
from orchestrator.platforms.youtube.token_store import (  # noqa: E402
    YouTubeTokenStore,
    TokenData as YTTokenData,
)


# ── TokenData.access_valid fail-closed ──────────────────────────────────────

def test_token_data_zero_expires_not_valid():
    td = TokenData(access_token="tok", expires_at=0)
    assert td.access_valid() is False


def test_token_data_no_expiry_flag_valid():
    td = TokenData(access_token="tok", expires_at=0, no_expiry=True)
    assert td.access_valid() is True


def test_token_data_expired_not_valid():
    td = TokenData(access_token="tok", expires_at=time.time() - 100)
    assert td.access_valid() is False


def test_token_data_fresh_valid():
    td = TokenData(access_token="tok", expires_at=time.time() + 3600)
    assert td.access_valid() is True


def test_yt_token_data_zero_expires_not_valid():
    td = YTTokenData(access_token="tok", expires_at=0)
    assert td.access_valid() is False


# ── OAuthTokenStore fail-closed ─────────────────────────────────────────────

def test_oauth_expired_no_refresh_raises_auth_required(tmp_path: Path):
    path = tmp_path / "ig.json"
    store = OAuthTokenStore(
        "instagram", path,
        token_url="https://example.com/token",
        client_id="cid", client_secret="sec",
    )
    store.save(TokenData(
        access_token="stale",
        refresh_token="",
        expires_at=time.time() - 60,
    ))
    with pytest.raises(ModuleError) as ei:
        store.get_access_token()
    assert ei.value.code == ModuleErrorCode.AUTH_REQUIRED


def test_oauth_expired_no_client_secret_raises_auth_required(tmp_path: Path):
    path = tmp_path / "ig.json"
    store = OAuthTokenStore(
        "instagram", path,
        token_url="https://example.com/token",
        client_id="", client_secret="",
    )
    store.save(TokenData(
        access_token="stale",
        refresh_token="rt",
        expires_at=time.time() - 60,
    ))
    with pytest.raises(ModuleError) as ei:
        store.get_access_token()
    assert ei.value.code == ModuleErrorCode.AUTH_REQUIRED


def test_oauth_zero_expires_no_refresh_raises(tmp_path: Path):
    path = tmp_path / "ig.json"
    store = OAuthTokenStore("instagram", path, token_url="https://example.com/token")
    # write raw file with expires_at=0, no updated_at → invalid
    path.write_text(json.dumps({
        "access_token": "tok",
        "refresh_token": "",
        "expires_at": 0,
    }), encoding="utf-8")
    with pytest.raises(ModuleError) as ei:
        store.get_access_token()
    assert ei.value.code == ModuleErrorCode.AUTH_REQUIRED


def test_oauth_valid_token_returned(tmp_path: Path):
    path = tmp_path / "ig.json"
    store = OAuthTokenStore("instagram", path)
    store.save(TokenData(
        access_token="good",
        expires_at=time.time() + 7200,
    ))
    assert store.get_access_token() == "good"


def test_oauth_empty_file_returns_empty(tmp_path: Path):
    store = OAuthTokenStore("instagram", tmp_path / "missing.json")
    assert store.get_access_token() == ""


# ── YouTubeTokenStore fail-closed ───────────────────────────────────────────

def test_yt_expired_no_refresh_raises(tmp_path: Path):
    path = tmp_path / "yt.json"
    store = YouTubeTokenStore(path, client_id="cid", client_secret="sec")
    store.save(YTTokenData(
        access_token="stale",
        refresh_token="",
        expires_at=time.time() - 60,
    ))
    with pytest.raises(ModuleError) as ei:
        store.get_access_token()
    assert ei.value.code == ModuleErrorCode.AUTH_REQUIRED


def test_yt_expired_no_client_raises(tmp_path: Path):
    path = tmp_path / "yt.json"
    store = YouTubeTokenStore(path, client_id="", client_secret="")
    store.save(YTTokenData(
        access_token="stale",
        refresh_token="rt",
        expires_at=time.time() - 60,
    ))
    with pytest.raises(ModuleError) as ei:
        store.get_access_token()
    assert ei.value.code == ModuleErrorCode.AUTH_REQUIRED


def test_yt_missing_file_raises(tmp_path: Path):
    store = YouTubeTokenStore(tmp_path / "none.json")
    with pytest.raises(ModuleError) as ei:
        store.get_access_token()
    assert ei.value.code == ModuleErrorCode.AUTH_REQUIRED


def test_yt_valid_token_returned(tmp_path: Path):
    path = tmp_path / "yt.json"
    store = YouTubeTokenStore(path)
    store.save(YTTokenData(
        access_token="yt-good",
        expires_at=time.time() + 7200,
    ))
    assert store.get_access_token() == "yt-good"


# ── token_broker local-files (no docker) ────────────────────────────────────

def test_broker_no_docker_in_source():
    src = (ROOT / "scripts" / "token_broker.py").read_text(encoding="utf-8")
    # executable references must not call docker/psql
    for bad in ('docker exec', 'psql', 'LEGACY_DB_CONTAINER', 'platform-db'):
        assert bad not in src, f"forbidden platform/docker ref still present: {bad}"


def test_broker_token_for_local_file(tmp_path: Path, monkeypatch):
    import token_broker as tb

    tokens = tmp_path / "tokens"
    tokens.mkdir()
    (tokens / "youtube.json").write_text(json.dumps({
        "access_token": "AT1",
        "refresh_token": "RT1",
        "expires_at": 9999999999,
        "client_id": "cid",
    }), encoding="utf-8")
    monkeypatch.setattr(tb, "TOKENS_DIR", tokens)
    monkeypatch.setattr(tb, "ALLOWED", {"youtube", "instagram"})

    data = tb.token_for("youtube")
    assert data is not None
    assert data["token"] == "AT1"
    assert data["refresh_token"] == "RT1"
    assert data["client_id"] == "cid"


def test_broker_token_for_account_id(tmp_path: Path, monkeypatch):
    import token_broker as tb

    tokens = tmp_path / "tokens"
    tokens.mkdir()
    (tokens / "youtube__ACC1.json").write_text(json.dumps({
        "access_token": "AT-ACC1",
    }), encoding="utf-8")
    monkeypatch.setattr(tb, "TOKENS_DIR", tokens)
    monkeypatch.setattr(tb, "ALLOWED", {"youtube"})

    data = tb.token_for("youtube", "ACC1")
    assert data is not None
    assert data["token"] == "AT-ACC1"
    assert tb.token_for("youtube") is None  # no default file


def test_broker_rejects_bad_platform_id():
    import token_broker as tb
    with pytest.raises(ValueError):
        tb.build_token_sql("youtube", "bad';drop")
    with pytest.raises(ValueError):
        tb._safe_platform("bad platform")


def test_broker_build_token_sql_marker():
    import token_broker as tb
    assert tb.build_token_sql("youtube", "INT1") == "local-file:youtube__INT1"
    assert tb.build_token_sql("youtube", None) == "local-file:youtube"


def test_meta_tiktok_factories(tmp_path: Path):
    m = make_meta_token_store("instagram", tokens_path=tmp_path / "ig.json")
    assert "graph.facebook.com" in m.token_url
    t = make_tiktok_token_store(tokens_path=tmp_path / "tt.json")
    assert "tiktokapis.com" in t.token_url


def test_no_expiry_roundtrip(tmp_path: Path):
    path = tmp_path / "ig.json"
    store = OAuthTokenStore("instagram", path)
    store.set_tokens("forever", no_expiry=True)
    loaded = store.load()
    assert loaded is not None
    assert loaded.no_expiry is True
    assert loaded.access_valid() is True
    assert store.get_access_token() == "forever"


def test_policy_ttl_from_updated_at(tmp_path: Path):
    path = tmp_path / "ig.json"
    # Fresh updated_at → still valid within policy TTL
    path.write_text(json.dumps({
        "access_token": "ttl-tok",
        "expires_at": 0,
        "updated_at": time.time(),
    }), encoding="utf-8")
    store = OAuthTokenStore("instagram", path, no_expiry_policy_ttl=3600)
    assert store.get_access_token() == "ttl-tok"


def test_policy_ttl_expired(tmp_path: Path):
    path = tmp_path / "ig.json"
    path.write_text(json.dumps({
        "access_token": "old-tok",
        "expires_at": 0,
        "updated_at": time.time() - 7200,
    }), encoding="utf-8")
    store = OAuthTokenStore("instagram", path, no_expiry_policy_ttl=3600)
    with pytest.raises(ModuleError) as ei:
        store.get_access_token()
    assert ei.value.code == ModuleErrorCode.AUTH_REQUIRED


def test_yt_no_expiry_roundtrip(tmp_path: Path):
    path = tmp_path / "yt.json"
    store = YouTubeTokenStore(path)
    store.set_tokens("yt-forever", no_expiry=True)
    assert store.get_access_token() == "yt-forever"
