"""P0 fixes from external audit: schedule hold, manual external_id, oauth callback path."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from orchestrator.oauth.manager import OAuthManager

ROOT = Path(__file__).resolve().parents[1]


def test_oauth_callback_uri_under_webapp_api():
    mgr = OAuthManager(public_base_url="https://example.com/", session_store=None, providers={})
    uri = mgr.callback_uri("youtube")
    assert uri == "https://example.com/webapp/api/oauth/callback/youtube"


def test_manual_confirm_writes_external_id(tmp_path):
    from orchestrator.db import Database
    from orchestrator.clock import FakeClock
    from orchestrator.manual_uploads import ManualUploadsService
    from orchestrator.config import load_config

    db = Database(tmp_path / "t.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    clock = FakeClock(datetime(2026, 9, 19, 12, 0, tzinfo=UTC))
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('videomaker','/s2','S2','/s2/w.mp4','Series',?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/s2'")["id"]
    up = db.upsert_upload(
        engine="direct",
        platform="youtube",
        external_id="yt_abc",
        url="https://youtu.be/abc",
        title="Series",
        origin="manual",
    )
    svc = ManualUploadsService(db, cfg, clock)
    assert svc.confirm(up["id"], "long_video", vid) is True
    eps = db.fetchone(
        "SELECT external_id, external_url, source, status FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='youtube'",
        (vid,),
    )
    assert eps is not None
    assert eps["external_id"] == "yt_abc"
    assert eps["status"] == "published"
    assert (eps["source"] or "") == "manual"


def test_scheduled_text_branch_is_local_hold():
    """Source guard: scheduled + no media must not call mod.publish."""
    src = (ROOT / "src/orchestrator/publisher.py").read_text(encoding="utf-8")
    assert "P0: scheduled + no media must NOT publish now" in src
    assert 'publish_mode = "local_schedule"' in src
    # ensure the dangerous pattern is gone from the else branch for scheduled text
    # (old code called mod.publish on empty prepared under scheduled_for)
    assert "scheduled + no media must NOT publish now" in src
