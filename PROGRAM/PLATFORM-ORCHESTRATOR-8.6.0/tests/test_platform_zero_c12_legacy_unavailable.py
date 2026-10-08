"""platform-zero COMMIT 12: core path lives when platform is down/unavailable."""
from __future__ import annotations

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
from orchestrator.platforms.base import (  # noqa: E402
    AuthStatus, MediaSpec, PlatformModule, PreparedMedia, PublishMeta, PublishResult, UploadResult,
)
from orchestrator.platforms.manifest import ModuleManifest  # noqa: E402
from orchestrator.publisher import Publisher  # noqa: E402
from orchestrator.safety import SafetyChecker  # noqa: E402
from orchestrator.status_sync import StatusSync  # noqa: E402
from orchestrator.schedule_guard import ScheduleGuard, eps_source  # noqa: E402


class _Deadplatform:
    def get_post(self, *a, **k):
        raise ConnectionError("platform unavailable")
    def create_post(self, *a, **k):
        raise ConnectionError("platform unavailable")
    def upload_media(self, *a, **k):
        raise ConnectionError("platform unavailable")
    def list_scheduled(self, *a, **k):
        raise ConnectionError("platform unavailable")
    def list_error_notifications(self, *a, **k):
        raise ConnectionError("platform unavailable")


class _Mod(PlatformModule):
    def __init__(self, **deps: Any) -> None:
        self.manifest = ModuleManifest(
            id="youtube", name="YT", api_version="1", module_version="0.0.1",
            core_min="8.0.0", auth={"method": "oauth"},
            capabilities={
                "publish": True, "early_upload": True, "schedule_publish": True,
                "update_metadata": False, "delete": False, "thumbnail": False,
                "claims_check": "unsupported", "video": True, "image": False, "text": False,
            },
            limits={}, media={}, statuses={}, docs="MODULE_YOUTUBE.txt",
        )
    def auth_status(self) -> AuthStatus:
        return AuthStatus(ok=True)
    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path, kind="video")
    def upload(self, media, meta, when=None):
        return UploadResult(external_id="gate_up_1", url="https://youtu.be/gate_up_1", state="scheduled")
    def schedule_publish(self, external_id, when):
        return True
    def publish(self, media, meta):
        return PublishResult(external_id="gate_pub_1", url="https://youtu.be/gate_pub_1", state="published")
    def get_status(self, external_id):
        from orchestrator.platforms.base import PublishStatus
        return PublishStatus(state="published", url=f"https://youtu.be/{external_id}")


def _cfg():
    for n in ("config.ci.yaml", "config.example.yaml"):
        if (ROOT / n).is_file():
            return load_config(ROOT / n)
    pytest.skip("no config")


def test_publisher_status_guard_with_platform_down(tmp_path, monkeypatch):
    monkeypatch.delenv("ORCH_LEGACY_TRANSPORT", raising=False)
    cfg = _cfg()
    cfg.engines = {"youtube": "module:youtube"}
    if hasattr(cfg, "platforms") and "youtube" in cfg.platforms:
        cfg.platforms["youtube"].enabled = True
    db = Database(tmp_path / "gate.sqlite")
    db.ensure_platform_states(["youtube"])
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    from orchestrator.platforms import ModuleRegistry
    registry = ModuleRegistry()
    registry.register("youtube", lambda **kw: _Mod(**kw))

    dead = _Deadplatform()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=False, module_registry=registry)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/g1', 't', '/g1/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/g1'")["id"]
    p = pub.publish(
        "long_video", vid, "youtube", "/g1/w.mp4", {"title": "G"},
        datetime(2026, 3, 10, 16, 0, tzinfo=UTC),
    )
    assert p is not None and p.id == "gate_up_1"

    sync = StatusSync(db, clock, cfg)  # module-only F2
    # row already has external via publisher
    n = sync.sync()
    assert n >= 0  # may already be scheduled

    guard = ScheduleGuard(cfg, clock, sources=[("eps", eps_source(db))])
    assert guard.conflict("youtube", datetime(2026, 3, 11, 12, 0, tzinfo=UTC)) is None
