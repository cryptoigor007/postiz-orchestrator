
"""Docs are module-first."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_start_mentions_module_engines():
    t = (ROOT / "START.md").read_text(encoding="utf-8")
    assert "module" in t.lower()
    assert "gate_platform_zero" in t or "HARD_CUT" in t
