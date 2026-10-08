
"""F9/F10/F11/F12 smoke: webapp helpers exist."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "src/orchestrator/webapp_api.py").read_text()

def test_api_has_inventory_ops():
    assert "_remote_inventory" in src
    assert "_ops_status" in src
    assert "external_id" in src

def test_calendar_prefers_scheduled_for():
    assert "COALESCE(eps.scheduled_for" in src or "scheduled_for" in src
