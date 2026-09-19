from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.config import load_config
from orchestrator.reload import reload_config
from orchestrator.slots import apply_jitter


def test_jitter_changes_time():
    dt = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    j = apply_jitter(dt, 90)
    assert abs((j - dt).total_seconds()) <= 90


def test_reload_ok():
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    new, msg = reload_config(Path(__file__).resolve().parents[1] / "config.yaml", cfg)
    assert new is not None
    assert msg == "ok"
