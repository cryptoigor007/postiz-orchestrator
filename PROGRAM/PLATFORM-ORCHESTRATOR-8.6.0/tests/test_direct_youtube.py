from __future__ import annotations

import importlib

import pytest

def test_direct_youtube_engine_removed_from_active_runtime():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("orchestrator.engines.direct_youtube")
