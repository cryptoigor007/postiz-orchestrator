from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_manual_uploads_defaults_and_yaml():
    cfg = load_config(ROOT / "config.yaml")
    mu = cfg.manual_uploads
    assert mu.enabled is True
    assert mu.lookback_days == 60
    assert mu.page_size == 50
    assert mu.confidence_high > mu.confidence_medium
    assert mu.schedule_scan in ("off", "daily")
    assert mu.claim_policy in ("warn", "block")
