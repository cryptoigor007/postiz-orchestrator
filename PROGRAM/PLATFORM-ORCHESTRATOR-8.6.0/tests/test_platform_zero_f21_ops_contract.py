"""HARD_CUT transport contract."""

import pytest

from orchestrator.platforms import resolve_engine

def test_no_legacy_transport_is_active():
    for legacy in ("direct", "browser", "n8n", "postiz"):
        with pytest.raises(ValueError):
            resolve_engine(legacy)
