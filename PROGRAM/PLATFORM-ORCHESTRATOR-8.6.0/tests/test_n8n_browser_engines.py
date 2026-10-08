from __future__ import annotations

import importlib

import pytest

from orchestrator.platforms import resolve_engine

def test_legacy_transport_engine_names_are_rejected():
    for value in ("direct", "n8n", "browser"):
        with pytest.raises(ValueError):
            resolve_engine(value)

def test_legacy_transport_modules_are_not_importable_from_active_runtime():
    for name in (
        "orchestrator.engines.direct_youtube",
        "orchestrator.engines.n8n_engine",
        "orchestrator.engines.browser_engine",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)
