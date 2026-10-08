"""platform-zero COMMIT 7 / F2: StatusSync module-only path."""
from __future__ import annotations

import inspect
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.clock import FakeClock  # noqa: E402
from orchestrator.config import load_config  # noqa: E402
from orchestrator.db import Database  # noqa: E402
from orchestrator.platforms.base import AuthStatus, PlatformModule, PublishStatus  # noqa: E402
from orchestrator.platforms.manifest import ModuleManifest  # noqa: E402
from orchestrator.status_sync import StatusSync  # noqa: E402


class _Mod(PlatformModule):
    def __init__(self, **deps: Any) -> None:
        self.manifest = ModuleManifest(
            id="youtube", name="YT", api_version="1", module_version="0.0.1",
            core_min="8.0.0", auth={"method": "oauth"},
            capabilities={
                "publish": True, "early_upload": False, "schedule_publish": False,
                "update_metadata": False, "delete": False, "thumbnail": False,
                "claims_check": "unsupported", "video": True, "image": False, "text": False,
            },
            limits={}, media={}, statuses={}, docs="MODULE_YOUTUBE.txt",
        )
        self.calls: list[str] = []

    def auth_status(self) -> AuthStatus:
        return AuthStatus(ok=True)

    def get_status(self, external_id: str) -> PublishStatus:
        self.calls.append(external_id)
        return PublishStatus(state="published", url=f"https://youtu.be/{external_id}")


def _cfg():
    for name in ("config.ci.yaml", "config.example.yaml"):
        path = ROOT / name
        if path.is_file():
            return load_config(path)
    pytest.skip("no config")


def test_status_sync_module_without_platform(tmp_path, monkeypatch):
    cfg = _cfg()
    cfg.engines = dict(getattr(cfg, "engines", {}) or {})
    cfg.engines["youtube"] = "module:youtube"
    db = Database(tmp_path / "s.sqlite")
    db.ensure_platform_states(["youtube"])
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    db.execute(
        """
        INSERT INTO entity_platform_status
            (entity_type, entity_id, platform, status, external_id, scheduled_for, source)
        VALUES ('short', 1, 'youtube', 'scheduled', 'VID99', '2026-03-10T16:00:00+00:00', 'module')
        """
    )
    mod = _Mod()
    from orchestrator.platforms import ModuleRegistry
    registry = ModuleRegistry()
    registry.register("youtube", lambda **kw: mod)

    sync = StatusSync(db, clock, cfg, registry=registry)
    n = sync.sync()
    assert n >= 1
    assert "VID99" in mod.calls
    row = db.fetchone(
        "SELECT status, release_url FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=1 AND platform='youtube'"
    )
    assert row["status"] == "published"
    assert "VID99" in (row["release_url"] or "")


def test_status_sync_platform_none_ok_for_module_rows(tmp_path):
    cfg = _cfg()
    cfg.engines = {"youtube": "module:youtube"}
    db = Database(tmp_path / "s2.sqlite")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    mod = _Mod()
    from orchestrator.platforms import ModuleRegistry
    registry = ModuleRegistry()
    registry.register("youtube", lambda **kw: mod)
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, external_id, source) "
        "VALUES ('short', 2, 'youtube', 'scheduled', 'X1', 'module')"
    )
    sync = StatusSync(db, clock, cfg, registry=registry)
    n = sync.sync()
    assert n >= 1


def test_status_sync_no_platform_attr():
    """F2: StatusSync must not accept or store platform."""
    sig = inspect.signature(StatusSync.__init__)
    assert "platform" not in sig.parameters
    cfg = _cfg()
    from orchestrator.db import Database
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        db = Database(Path(td) / "t.sqlite")
        clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
        sync = StatusSync(db, clock, cfg)
        assert not hasattr(sync, "platform") or getattr(sync, "platform", None) is None
        # source must not reference self.platform
        src = Path(__file__).resolve().parents[1] / "src" / "orchestrator" / "status_sync.py"
        text = src.read_text(encoding="utf-8")
        assert "self.platform" not in text
        assert "Ошибка platform" not in text
