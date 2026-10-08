"""TikTok inbox JSON persistence across module instances."""
from __future__ import annotations

from orchestrator.platforms.base import MediaSpec, PublishMeta
from orchestrator.platforms.tiktok.module import TikTokModule


def test_tiktok_inbox_persists(tmp_path, monkeypatch):
    store = tmp_path / "tiktok_inbox.json"
    monkeypatch.setenv("TIKTOK_INBOX_PATH", str(store))
    mod = TikTokModule(dry_run=True, publish_mode="inbox")
    media = mod.prepare(MediaSpec(path="", kind="video"))
    res = mod.publish(media, PublishMeta(title="t1"))
    assert res.state == "uploaded_inbox"
    assert store.is_file()
    mod2 = TikTokModule(dry_run=True, publish_mode="inbox")
    st = mod2.get_status(res.external_id)
    assert st.state == "uploaded_inbox"
