from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from orchestrator.config import load_config
from orchestrator.platforms import resolve_engine
ROOT = Path(__file__).resolve().parents[1]

def test_engines_default_and_mapping():
    cfg = load_config(ROOT / "config.ci.yaml")
    assert isinstance(cfg.engines, dict)
    yt = cfg.engine_for("youtube")
    assert "youtube" in str(yt) or yt == "direct"
    r = resolve_engine("module:youtube")
    assert r.kind == "module"
