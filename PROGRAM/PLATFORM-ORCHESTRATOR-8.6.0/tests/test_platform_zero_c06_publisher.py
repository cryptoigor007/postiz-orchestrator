"""platform-zero C6/F3: Publisher module-only; no platform / LEGACY flags."""
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
from orchestrator.platforms.base import (  # noqa: E402
    AuthStatus,
    MediaSpec,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    UploadResult,
)
from orchestrator.platforms.manifest import ModuleManifest  # noqa: E402
from orchestrator.publisher import Publisher  # noqa: E402
from orchestrator.safety import SafetyChecker  # noqa: E402


class _MockYtModule(PlatformModule):
    def __init__(self, **deps: Any) -> None:
        self.manifest = ModuleManifest(
            id="youtube",
            name="YouTube Mock",
            api_version="1",
            module_version="0.0.1-test",
            core_min="8.0.0",
            auth={"method": "oauth"},
            capabilities={
                "publish": True,
                "early_upload": True,
                "schedule_publish": True,
                "update_metadata": False,
                "delete": False,
                "thumbnail": False,
                "claims_check": "unsupported",
                "video": True,
                "image": False,
                "text": False,
                "list_uploads": False,
                "list_scheduled": False,
                "list_private": False,
                "scan_mode": "auto",
                "schedule_owner": "platform",
            },
            limits={},
            media={},
            statuses={},
            docs="MODULE_YOUTUBE.txt",
        )
        self.calls: list[str] = []

    def auth_status(self) -> AuthStatus:
        return AuthStatus(ok=True, account_id="mock")

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path or "", kind=media.kind or "video")

    def upload(self, media: PreparedMedia, meta: PublishMeta, when=None) -> UploadResult:
        self.calls.append(f"upload:{meta.title}")
        return UploadResult(external_id="yt_mock_up_1", url="https://youtu.be/yt_mock_up_1")

    def schedule_publish(self, external_id: str, when) -> None:
        self.calls.append(f"sched:{external_id}")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        self.calls.append(f"pub:{meta.title}")
        return PublishResult(
            external_id="yt_mock_pub_1",
            url="https://youtu.be/yt_mock_pub_1",
            state="published",
        )


def _cfg():
    for name in ("config.ci.yaml", "config.example.yaml"):
        path = ROOT / name
        if path.is_file():
            return load_config(path)
    pytest.skip("no config")


@pytest.fixture
def env(tmp_path, monkeypatch):
    cfg = _cfg()
    cfg.engines = dict(getattr(cfg, "engines", {}) or {})
    cfg.engines["youtube"] = "module:youtube"
    db = Database(tmp_path / "p.sqlite")
    db.ensure_platform_states(["youtube"])
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    safety = SafetyChecker(db, cfg, clock)
    mod = _MockYtModule()
    from orchestrator.platforms import ModuleRegistry
    registry = ModuleRegistry()
    registry.register("youtube", lambda **kw: mod)
    pub = Publisher(db, cfg, safety, clock, dry_run=False, module_registry=registry)
    return db, cfg, clock, safety, pub, mod, monkeypatch


def test_module_path_scheduled(env):
    db, cfg, clock, safety, pub, mod, monkeypatch = env
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/m1', 't', '/m1/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/m1'")["id"]
    p = pub.publish(
        "long_video", vid, "youtube", "/m1/w.mp4",
        {"title": "T"}, datetime(2026, 3, 10, 16, 0, tzinfo=UTC),
    )
    assert p is not None
    assert p.id == "yt_mock_up_1"
    row = db.fetchone(
        "SELECT status, external_id, source FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='youtube'",
        (vid,),
    )
    assert row["status"] == "scheduled"
    assert row["external_id"] == "yt_mock_up_1"
    assert row["source"] == "module"


def test_module_path_immediate(env):
    db, cfg, clock, safety, pub, mod, monkeypatch = env
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/m2', 't', '/m2/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/m2'")["id"]
    p = pub.publish("long_video", vid, "youtube", "/m2/w.mp4", {"title": "Now"})
    assert p is not None
    assert p.id == "yt_mock_pub_1"
    assert p.status == "published"


def test_no_module_raises(env):
    db, cfg, clock, safety, pub, mod, monkeypatch = env
    cfg.engines["youtube"] = "legacy_transport"
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/m4', 't', '/m4/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/m4'")["id"]
    # Hard-cut: engines.youtube=platform fails at engine_for / select_engine
    with pytest.raises((ValueError, RuntimeError)):
        pub.publish(
            "long_video", vid, "youtube", "/m4/w.mp4",
            {"title": "T"}, datetime(2026, 3, 10, 16, 0, tzinfo=UTC),
        )


def test_publisher_no_platform_kwarg():
    sig = inspect.signature(Publisher.__init__)
    assert "platform" not in sig.parameters
    src = (ROOT / "src/orchestrator/publisher.py").read_text(encoding="utf-8")
    assert "ORCH_LEGACY_TRANSPORT" not in src
    assert "ORCH_MODULE_PUBLISH" not in src
    assert "self.platform" not in src


def test_lease_recovery_stuck_publishing(env):
    """F3 must-fix: expired lease_until allows re-claim of stuck publishing."""
    db, cfg, clock, safety, pub, mod, monkeypatch = env
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/m7', 't', '/m7/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/m7'")["id"]
    past = "2020-01-01T00:00:00+00:00"
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, external_id, lease_until, attempt) "
        "VALUES ('long_video', ?, 'youtube', 'publishing', NULL, ?, 1)",
        (vid, past),
    )
    p = pub.publish(
        "long_video", vid, "youtube", "/m7/w.mp4",
        {"title": "Recover"}, datetime(2026, 3, 10, 16, 0, tzinfo=UTC),
    )
    assert p is not None
    assert p.id == "yt_mock_up_1"
