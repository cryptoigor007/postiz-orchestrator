"""F1: config has no operational platform keys; account_id / module_create_per_hour present."""
from __future__ import annotations

from pathlib import Path

import yaml

from orchestrator.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_example_config_no_platform_operational_keys():
    raw = (ROOT / "config.example.yaml").read_text(encoding="utf-8")
    assert "legacy_create_per_hour" not in raw
    assert "test_integration_ids" not in raw
    assert "integration_id:" not in raw
    data = yaml.safe_load(raw)
    assert "module_create_per_hour" in data["limits"]
    assert "test_account_ids" in data["test_publish"]
    yt = data["platforms"]["youtube"]
    assert "account_id" in yt


def test_ci_config_account_ids():
    cfg = load_config(ROOT / "config.ci.yaml")
    assert cfg.platforms["youtube"].account_id == "ci-youtube-account"
    assert cfg.platforms["telegram"].account_id == "ci-telegram-account"
    assert cfg.limits.module_create_per_hour == 60
    assert "ci-youtube-account" in cfg.test_publish.test_account_ids


def test_legacy_integration_id_maps_to_account_id(tmp_path):
    p = tmp_path / "legacy.yaml"
    p.write_text(
        """
schedules: {x: {type: long_video, source: videomaker, days: [mon], time: "10:00"}}
platforms:
  youtube:
    enabled: true
    integration_id: legacy-yt
limits:
  legacy_create_per_hour: 42
test_publish:
  test_integration_ids: ["legacy-yt"]
""",
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.platforms["youtube"].account_id == "legacy-yt"
    assert cfg.limits.module_create_per_hour == 42
    assert cfg.test_publish.test_account_ids == ["legacy-yt"]
