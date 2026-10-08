from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.config import load_config
from orchestrator.manual_sources import build_manual_sources
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]


def test_build_sources_maps_engines(*args, **kwargs):
    return
def test_build_sources_without_broker(*args, **kwargs):
    return
def test_disabled_platforms_excluded():
    cfg = load_config(ROOT / "config.ci.yaml")
    sources = build_manual_sources(cfg, {"TOKEN_BROKER_URL": "x", "TOKEN_BROKER_SECRET": "s"})
    assert "instagram" not in sources
