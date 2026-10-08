
"""F16 TikTok inbox: uploaded_inbox ≠ published; public list only."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from orchestrator.platforms.tiktok.module import TikTokModule
from orchestrator.platforms.base import MediaSpec, PublishMeta

def test_tiktok_inbox_not_published():
    m = TikTokModule(dry_run=True, publish_mode="inbox")
    assert (m.manifest.limits or {}).get("publish_mode") == "inbox" or m._publish_mode == "inbox"
    prep = m.prepare(MediaSpec(path="/x/v.mp4", kind="video"))
    pr = m.publish(prep, PublishMeta(title="tt"))
    assert pr.state == "uploaded_inbox"
    assert pr.state != "published"
    st = m.get_status(pr.external_id)
    assert st.state == "uploaded_inbox"
    assert st.state != "published"

def test_tiktok_list_remote_public_only():
    m = TikTokModule(dry_run=True)
    assert m.list_remote() == []
