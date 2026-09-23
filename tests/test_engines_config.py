from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_engines_default_and_mapping():
    cfg = load_config(ROOT / "config.yaml")
    assert isinstance(cfg.engines, dict)
    assert cfg.engine_for("youtube") == "direct"
    assert cfg.engine_for("telegram") == "postiz"
    # unknown platform falls back to postiz
    assert cfg.engine_for("mastodon") == "postiz"
