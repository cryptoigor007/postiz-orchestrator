"""H6: token_store шаблон Meta/TikTok — без live ключей."""
from __future__ import annotations

import time
from pathlib import Path

import httpx

from orchestrator.platforms.token_store import (
    META_TOKEN_URL,
    TIKTOK_TOKEN_URL,
    OAuthTokenStore,
    TokenData,
    make_meta_token_store,
    make_tiktok_token_store,
)


class _Transport(httpx.BaseTransport):
    def __init__(self, handler):
        self.handler = handler
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self.handler(request)

def test_save_load_roundtrip(tmp_path: Path):
    path = tmp_path / "instagram.json"
    store = OAuthTokenStore("instagram", path, token_url=META_TOKEN_URL)
    store.set_tokens("acc_1", refresh_token="ref_1", expires_in=3600, scope="ig")
    loaded = store.load()
    assert loaded and loaded.access_token == "acc_1" and loaded.refresh_token == "ref_1"

def test_access_valid_skew():
    assert not TokenData(access_token="x", expires_at=time.time() + 60).access_valid(skew=120)
    assert TokenData(access_token="x", expires_at=time.time() + 3600).access_valid(skew=600)

def test_get_access_without_refresh_returns_cached(tmp_path: Path):
    store = OAuthTokenStore("tiktok", tmp_path / "tiktok.json", token_url=TIKTOK_TOKEN_URL)
    store.set_tokens("tok", expires_in=7200)
    assert store.get_access_token() == "tok"

def test_refresh_success(tmp_path: Path):
    from orchestrator.http_client import ModuleHttpClient
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "new_acc", "token_type": "bearer", "expires_in": 5184000})
    http = ModuleHttpClient(platform="instagram", module_version="0.2.0", transport=_Transport(handler), max_retries=1)
    store = OAuthTokenStore("instagram", tmp_path / "ig.json", token_url=META_TOKEN_URL,
                            client_id="app_id", client_secret="app_secret", http=http)
    store.set_tokens("old", refresh_token="ref", expires_in=1)
    assert store.get_access_token(force_refresh=True) == "new_acc"

def test_make_meta_and_tiktok_factories(tmp_path: Path):
    assert make_meta_token_store("facebook", tokens_path=tmp_path / "fb.json").token_url == META_TOKEN_URL
    assert make_tiktok_token_store(tokens_path=tmp_path / "tt.json").token_url == TIKTOK_TOKEN_URL

def test_empty_file_returns_empty_token(tmp_path: Path):
    assert OAuthTokenStore("instagram", tmp_path / "missing.json").get_access_token() == ""
