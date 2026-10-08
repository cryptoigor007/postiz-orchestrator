
"""F19 module reconciliation."""
from __future__ import annotations
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.reconciliation import ModuleReconciliation
from orchestrator.platforms.base import PlatformModule, AuthStatus, PublishStatus
from orchestrator.platforms.manifest import ModuleManifest

class _Mod(PlatformModule):
    def __init__(self, **kw):
        self.manifest = ModuleManifest(
            id="youtube", name="YT", api_version="1", module_version="0.0.1",
            core_min="8.0.0", auth={"method": "oauth"},
            capabilities={"publish": True}, limits={}, media={}, statuses={}, docs="",
        )
        self.missing = set()
    def auth_status(self):
        return AuthStatus(ok=True)
    def get_status(self, external_id: str):
        if external_id in self.missing:
            return None
        return PublishStatus(state="published", url=f"https://youtu.be/{external_id}")

def test_recon_updates_published(tmp_path):
    cfg = load_config(ROOT / "config.ci.yaml")
    cfg.engines = {"youtube": "module:youtube"}
    db = Database(tmp_path / "r.sqlite")
    clock = FakeClock(datetime(2026, 5, 1, 12, 0, tzinfo=UTC))
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, external_id) "
        "VALUES ('short', 1, 'youtube', 'scheduled', 'VID1')"
    )
    mod = _Mod()
    from orchestrator.platforms import ModuleRegistry
    registry = ModuleRegistry()
    registry.register("youtube", lambda **kw: mod)
    recon = ModuleReconciliation(db, cfg, clock, module_registry=registry)
    r = recon.run()
    assert r.checked >= 1
    row = db.fetchone("SELECT status FROM entity_platform_status WHERE entity_id=1")
    assert row["status"] == "published"

def test_main_has_module_recon():
    src = (ROOT / "src/orchestrator/main.py").read_text()
    assert "ModuleReconciliation" in src
    assert "recon = None" not in src or "ModuleReconciliation" in src
