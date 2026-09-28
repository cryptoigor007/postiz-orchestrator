"""P2-R2: publisher path kind=module under ORCH_MODULE_PUBLISH flag."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.platforms.base import (
    AuthStatus,
    MediaSpec,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    UploadResult,
)
from orchestrator.platforms.manifest import ModuleManifest
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker


class _MockYtModule(PlatformModule):
    def __init__(self, **deps: Any) -> None:
        self.manifest = ModuleManifest(
            id="youtube", name="YouTube Mock", api_version="1",
            module_version="0.0.1-test", core_min="8.0.0",
            auth={"method": "oauth"},
            capabilities={
                "publish": True, "early_upload": True, "schedule_publish": True,
                "update_metadata": False, "delete": False, "thumbnail": False,
                "claims_check": "unsupported", "video": True, "image": False, "text": False,
            },
            limits={}, media={}, statuses={}, docs="",
        )
    def auth_status(self) -> AuthStatus:
        return AuthStatus(ok=True, account="mock")
    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path, kind=media.kind or "video")
    def upload(self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None) -> UploadResult:
        return UploadResult(external_id="yt_mock_up_1", url="", state="uploaded")
    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        return True
    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        return PublishResult(external_id="yt_mock_pub_1", url="https://youtu.be/mock", state="published")

@pytest.fixture
def env(tmp_path, monkeypatch):
    db = Database(tmp_path / "t.sqlite")
    db.ensure_platform_states(["youtube"])
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    cfg.engines = dict(getattr(cfg, "engines", {}) or {})
    cfg.engines["youtube"] = "module:youtube"
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    from orchestrator.platforms import default_registry
    default_registry().register("youtube", lambda **kw: _MockYtModule(**kw))
    return db, cfg, clock, postiz, safety, pub, monkeypatch

def test_module_path_off_by_default_uses_postiz(env):
    db, cfg, clock, postiz, safety, pub, monkeypatch = env
    monkeypatch.delenv("ORCH_MODULE_PUBLISH", raising=False)
    db.execute("INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) VALUES ('v', '/m1', 't', '/m1/w.mp4', ?)", (clock.now().isoformat(),))
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/m1'")["id"]
    p = pub.publish("long_video", vid, "youtube", "/m1/w.mp4", {"title": "T"}, datetime(2026, 3, 10, 16, 0, tzinfo=UTC))
    assert p is not None and len(postiz.posts) >= 1 and not str(p.id).startswith("yt_mock_")

def test_module_path_on_uses_module(env):
    db, cfg, clock, postiz, safety, pub, monkeypatch = env
    monkeypatch.setenv("ORCH_MODULE_PUBLISH", "1")
    db.execute("INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) VALUES ('v', '/m2', 't', '/m2/w.mp4', ?)", (clock.now().isoformat(),))
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/m2'")["id"]
    p = pub.publish("long_video", vid, "youtube", "/m2/w.mp4", {"title": "T"}, datetime(2026, 3, 10, 16, 0, tzinfo=UTC))
    assert p is not None and p.id == "yt_mock_up_1" and len(postiz.posts) == 0
    row = db.fetchone("SELECT status, postiz_post_id FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=? AND platform='youtube'", (vid,))
    assert row["status"] == "scheduled" and row["postiz_post_id"] == "yt_mock_up_1"

def test_module_path_immediate_publish(env):
    db, cfg, clock, postiz, safety, pub, monkeypatch = env
    monkeypatch.setenv("ORCH_MODULE_PUBLISH", "1")
    db.execute("INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) VALUES ('v', '/m3', 't', '/m3/w.mp4', ?)", (clock.now().isoformat(),))
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/m3'")["id"]
    p = pub.publish("long_video", vid, "youtube", "/m3/w.mp4", {"title": "Now"}, None)
    assert p is not None and p.id == "yt_mock_pub_1" and p.status == "published"

def test_postiz_engine_unchanged_with_flag(env):
    db, cfg, clock, postiz, safety, pub, monkeypatch = env
    monkeypatch.setenv("ORCH_MODULE_PUBLISH", "1")
    cfg.engines["youtube"] = "postiz"
    db.execute("INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) VALUES ('v', '/m4', 't', '/m4/w.mp4', ?)", (clock.now().isoformat(),))
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/m4'")["id"]
    p = pub.publish("long_video", vid, "youtube", "/m4/w.mp4", {"title": "T"}, datetime(2026, 3, 10, 16, 0, tzinfo=UTC))
    assert p is not None and len(postiz.posts) >= 1
