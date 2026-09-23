from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.config import load_config


def test_load_config():
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    assert "youtube" in cfg.platforms
    assert cfg.platforms["youtube"].daily_limit == 7
    assert cfg.safety.min_interval_minutes == 25
    assert cfg.timezone == "Europe/Moscow"
    assert cfg.file_stability_cycles == 2
