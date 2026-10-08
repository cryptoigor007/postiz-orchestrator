
"""F14 Instagram: B2 url path dry_run; schedule_owner orchestrator; no schedule_publish."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from orchestrator.platforms.instagram.module import InstagramModule
from orchestrator.platforms.base import MediaSpec, PublishMeta, NotSupported
import pytest

def test_ig_manifest_orchestrator_owner():
    m = InstagramModule(dry_run=True)
    assert m.manifest.capabilities.get("schedule_owner") == "orchestrator"
    assert m.manifest.capabilities.get("schedule_publish") is False

def test_ig_dry_publish_container_flow():
    m = InstagramModule(dry_run=True)
    prep = m.prepare(MediaSpec(path="/x/v.mp4", kind="video"))
    pr = m.publish(prep, PublishMeta(title="IG", description="cap"))
    assert pr.external_id
    assert pr.state == "published"

def test_ig_upload_returns_container_id():
    m = InstagramModule(dry_run=True)
    prep = m.prepare(MediaSpec(path="/x/v.mp4", kind="video"))
    up = m.upload(prep, PublishMeta(title="c"))
    assert up.external_id  # container id

def test_ig_schedule_not_supported():
    m = InstagramModule(dry_run=True)
    with pytest.raises(NotSupported):
        m.schedule_publish("x", __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
