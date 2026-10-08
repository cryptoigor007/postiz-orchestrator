from __future__ import annotations

import pytest

from orchestrator.platforms import resolve_engine

def test_only_native_module_engine_is_resolvable():
    resolved = resolve_engine("module:telegram")
    assert resolved.kind == "module"
    assert resolved.module_id == "telegram"
    for legacy in ("direct", "browser", "n8n", "postiz"):
        with pytest.raises(ValueError):
            resolve_engine(legacy)
