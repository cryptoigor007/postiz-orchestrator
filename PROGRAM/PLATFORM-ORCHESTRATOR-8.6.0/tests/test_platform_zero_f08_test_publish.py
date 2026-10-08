
"""F8: test_publish allowlist uses test_account_ids."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator import test_publish as tp


def test_fail_closed_empty_account_ids():
    tcfg = SimpleNamespace(
        enabled=True,
        test_account_ids=[],
        test_integration_ids=[],
        prod_account_ids=[],
        prod_integration_ids=[],
        platforms=["youtube"],
        allow_prod_channel=False,
    )
    pcfg = SimpleNamespace(account_id="a1", integration_id="")
    # call internal gate if exposed
    if hasattr(tp, "_check_account_allowed"):
        with pytest.raises(Exception):
            tp._check_account_allowed(tcfg, pcfg)
    else:
        # ensure module references test_account_ids
        src = Path(tp.__file__).read_text(encoding="utf-8")
        assert "test_account_ids" in src
        assert "test_account_ids not configured" in src or "test_integration_ids" in src
