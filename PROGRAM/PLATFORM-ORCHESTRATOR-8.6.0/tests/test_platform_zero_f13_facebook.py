
"""F13 Facebook: Reels/Video dry_run + schedule + list partial + honest caps."""
from __future__ import annotations
import sys
from datetime import UTC, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from orchestrator.platforms.facebook.module import FacebookModule
from orchestrator.platforms.base import MediaSpec, PublishMeta, NotSupported

def test_fb_dry_publish_video():
    m = FacebookModule(dry_run=True)
    assert m.manifest.capabilities.get("schedule_publish") is True
    assert m.manifest.capabilities.get("scan_mode") in ("auto", "published_only")
    prep = m.prepare(MediaSpec(path="/x/long.mp4", kind="video"))
    pr = m.publish(prep, PublishMeta(title="T", description="D"))
    assert pr.external_id.startswith("fb-dry")
    assert pr.state == "published"

def test_fb_short_reels_path():
    m = FacebookModule(dry_run=True)
    prep = m.prepare(MediaSpec(path="/x/short_clip.mp4", kind="video"))
    pr = m.publish(prep, PublishMeta(title="S", extra={"is_short": True}))
    assert pr.external_id

def test_fb_upload_scheduled():
    m = FacebookModule(dry_run=True)
    prep = m.prepare(MediaSpec(path="/x/v.mp4", kind="video"))
    up = m.upload(prep, PublishMeta(title="U"), when=datetime(2026, 4, 1, 16, 0, tzinfo=UTC))
    assert up.external_id
    assert up.state in ("scheduled", "uploaded")

def test_fb_list_remote_partial():
    m = FacebookModule(dry_run=True)
    items = m.list_remote()
    assert isinstance(items, list)
