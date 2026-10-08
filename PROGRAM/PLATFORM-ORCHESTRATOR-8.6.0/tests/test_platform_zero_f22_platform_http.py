
"""F22: platform modules dry_run HTTP-shaped contracts."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from datetime import datetime, timezone
from orchestrator.platforms.base import MediaSpec, PublishMeta, NotSupported
from orchestrator.platforms.facebook.module import FacebookModule
from orchestrator.platforms.instagram.module import InstagramModule
from orchestrator.platforms.threads.module import ThreadsModule
from orchestrator.platforms.tiktok.module import TikTokModule

def test_facebook_reels_and_list_dry():
    m = FacebookModule(dry_run=True, graph_version="v21.0")
    prep = m.prepare(MediaSpec(path="/x/v.mp4", kind="video"))
    pr = m.publish(prep, PublishMeta(title="reel", extra={"is_short": True}))
    assert pr.external_id and pr.state in ("published", "scheduled")
    assert m.list_remote(limit=5) is not None
    assert m.check_claims("x").supported is False

def test_facebook_schedule_upload_dry():
    m = FacebookModule(dry_run=True)
    prep = m.prepare(MediaSpec(path="/x/long.mp4", kind="video"))
    when = datetime.now(timezone.utc)
    up = m.upload(prep, PublishMeta(title="long"), when=when)
    assert up.external_id

def test_instagram_container_then_status():
    m = InstagramModule(dry_run=True)
    prep = m.prepare(MediaSpec(path="/x/v.mp4", kind="video"))
    up = m.upload(prep, PublishMeta(title="ig"))
    assert up.external_id  # container
    st = m.get_status(up.external_id)
    assert st is not None

def test_threads_daily_and_list():
    m = ThreadsModule(dry_run=True)
    assert int(m.manifest.limits.get("daily_default") or 0) == 3
    prep = m.prepare(MediaSpec(path="", kind="text"))
    pr = m.publish(prep, PublishMeta(title="hi"))
    assert pr.external_id
    assert isinstance(m.list_remote(), list)

def test_tiktok_inbox_and_public_list():
    m = TikTokModule(dry_run=True, publish_mode="inbox")
    prep = m.prepare(MediaSpec(path="/x/v.mp4", kind="video"))
    pr = m.publish(prep, PublishMeta(title="tt"))
    assert pr.state == "uploaded_inbox"
    assert pr.state != "published"
    assert m.list_remote() == [] or all(
        (x.get("state") or x.get("status")) != "uploaded_inbox"
        for x in (m.list_remote() or [])
    )

def test_instagram_schedule_not_supported():
    m = InstagramModule(dry_run=True)
    import pytest
    with pytest.raises(NotSupported):
        m.schedule_publish("c1", datetime.now(timezone.utc))
