from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.config import load_config
from orchestrator.postiz import MockPostizClient
from orchestrator.manual_sources import build_manual_sources
from orchestrator.engines.postiz_engine import PostizEngine
from orchestrator.engines.direct_youtube import YouTubeEngine

ROOT = Path(__file__).resolve().parents[1]


def test_build_sources_maps_engines():
    cfg = load_config(ROOT / "config.yaml")
    env = {"TOKEN_BROKER_URL": "http://broker:9099", "TOKEN_BROKER_SECRET": "s"}
    sources = build_manual_sources(cfg, MockPostizClient(), env)
    assert isinstance(sources["telegram"], PostizEngine)
    assert isinstance(sources["youtube"], YouTubeEngine)


def test_build_sources_without_broker():
    cfg = load_config(ROOT / "config.yaml")
    sources = build_manual_sources(cfg, MockPostizClient(), {})
    assert "youtube" not in sources  # direct requires broker
    assert isinstance(sources["telegram"], PostizEngine)


def test_disabled_platforms_excluded():
    cfg = load_config(ROOT / "config.yaml")
    sources = build_manual_sources(cfg, MockPostizClient(), {"TOKEN_BROKER_URL": "x", "TOKEN_BROKER_SECRET": "s"})
    assert "instagram" not in sources
