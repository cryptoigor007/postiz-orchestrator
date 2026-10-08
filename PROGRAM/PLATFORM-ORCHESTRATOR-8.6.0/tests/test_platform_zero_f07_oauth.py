
"""F7: OAuth PKCE + graph version from config; consume-once sessions."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.oauth.manager import make_meta_provider, meta_graph_version


def test_meta_graph_version_default(monkeypatch):
    monkeypatch.delenv("META_GRAPH_VERSION", raising=False)
    assert meta_graph_version() == "v26.0"


def test_meta_graph_version_env(monkeypatch):
    monkeypatch.setenv("META_GRAPH_VERSION", "v19.0")
    assert meta_graph_version() == "v19.0"


def test_make_meta_provider_urls():
    p = make_meta_provider(graph_version="v18.0")
    assert "v18.0" in p.authorize_url
    assert "v18.0" in p.token_url
