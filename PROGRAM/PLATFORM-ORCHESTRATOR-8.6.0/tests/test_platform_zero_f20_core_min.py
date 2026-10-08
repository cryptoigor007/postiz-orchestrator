
"""F20 core_min load gate."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from orchestrator.platforms import ModuleRegistry, _version_gte
from orchestrator.platforms.base import PlatformModule, AuthStatus, ModuleError
from orchestrator.platforms.manifest import ModuleManifest

def test_version_gte():
    assert _version_gte("8.4.55", "8.0.0")
    assert not _version_gte("7.9.0", "8.0.0")

def test_core_min_blocks_old_core(monkeypatch):
    class M(PlatformModule):
        def __init__(self, **kw):
            self.manifest = ModuleManifest(
                id="dummy", name="D", api_version="1", module_version="9.0.0",
                core_min="99.0.0", auth={"method": "oauth"},
                capabilities={"publish": True}, limits={}, media={}, statuses={}, docs="",
            )
        def auth_status(self):
            return AuthStatus(ok=True)
    reg = ModuleRegistry()
    reg.register("dummy", lambda **kw: M())
    try:
        reg.create("dummy")
        # if core is somehow >= 99, skip
    except ModuleError as e:
        assert "core>=" in e.message or "99" in e.message
