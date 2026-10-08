from __future__ import annotations

from pathlib import Path
import yaml


def test_provider_catalog_separates_live_from_code_state():
    path = Path(__file__).resolve().parents[1] / "docs" / "provider-catalog.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["runtime_contract"] == "implementation_state_is_not_live"
    providers = data["providers"]
    assert len(providers) == 42
    assert all(p.get("live_status") == "NOT_LIVE" for p in providers)
