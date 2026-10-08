from __future__ import annotations

import json
import time
from pathlib import Path

from orchestrator.token_lifecycle import TokenLifecycleStore


def test_token_refresh_not_due_does_not_network(tmp_path: Path):
    store = TokenLifecycleStore(tmp_path)
    store.rotate("instagram", "a1", access_token="A", refresh_token="R", expires_at=time.time() + 7200)
    assert store.refresh_expiring("instagram", "a1", skew_sec=600) == "not_due"
    assert json.loads((tmp_path / "instagram__a1.json").read_text())["access_token"] == "A"


def test_token_refresh_unsupported_platform_is_explicit(tmp_path: Path):
    store = TokenLifecycleStore(tmp_path)
    store.rotate("x", "a1", access_token="A", refresh_token="R", expires_at=time.time() + 30)
    assert store.refresh_expiring("x", "a1") == "unsupported"
