from __future__ import annotations
from orchestrator.db import Database
from orchestrator.publisher import Publisher


def test_immutable_content_revision_and_distribution_target(tmp_path):
    db = Database(tmp_path / "c8.sqlite")
    from orchestrator.config import load_config
    from orchestrator.clock import FakeClock
    from orchestrator.safety import SafetyChecker
    cfg=load_config("config.ci.yaml")
    pub=Publisher(db,cfg,SafetyChecker(db,cfg,FakeClock()),FakeClock(),dry_run=True)
    rev=pub._ensure_content_revision("short",1,{"title":"A"},None)
    assert len(rev)==64
    tid=pub._ensure_distribution_target("short",1,"youtube","a",rev,None)
    assert db.fetchone("SELECT revision_hash,status FROM distribution_targets WHERE id=?",(tid,))["status"]=="publishing"
    rev2=pub._ensure_content_revision("short",1,{"title":"B"},None)
    assert rev != rev2
    assert len(db.fetchall("SELECT * FROM content_revisions WHERE entity_type='short' AND entity_id=1"))==2


def test_schedule_artifacts_are_atomic(tmp_path):
    from datetime import UTC, datetime
    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.safety import SafetyChecker

    db = Database(tmp_path / "atomic.sqlite")
    cfg = load_config("config.ci.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    pub = Publisher(db, cfg, SafetyChecker(db, cfg, clock), clock, dry_run=False)
    rev, target = pub._ensure_schedule_artifacts(
        "long_video", 9, "youtube", "yt-a1", {"title": "Atomic"}, "/video.mp4",
        datetime(2026, 3, 10, 16, 0, tzinfo=UTC),
    )
    row = db.fetchone(
        "SELECT dt.account_id, dt.revision_hash, cr.content_json, cr.media_path "
        "FROM distribution_targets dt JOIN content_revisions cr ON cr.revision_hash=dt.revision_hash "
        "WHERE dt.id=?", (target,),
    )
    assert row == {"account_id": "yt-a1", "revision_hash": rev, "content_json": '{"title": "Atomic"}', "media_path": "/video.mp4"}


def test_schedule_snapshot_failure_is_fail_closed(tmp_path, monkeypatch):
    from datetime import UTC, datetime
    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.safety import SafetyChecker

    db = Database(tmp_path / "fail.sqlite")
    cfg = load_config("config.ci.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    pub = Publisher(db, cfg, SafetyChecker(db, cfg, clock), clock, dry_run=False)
    monkeypatch.setattr(pub, "_ensure_schedule_artifacts", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    out = pub.publish(
        "long_video", 12, "youtube", None, {"title": "will fail"},
        datetime(2026, 3, 10, 16, 0, tzinfo=UTC), account_id="yt-a1",
    )
    assert out is None
    eps = db.fetchone(
        "SELECT status, last_error, lease_until FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=12 AND platform='youtube' AND account_id='yt-a1'"
    )
    assert eps["status"] == "error"
    assert eps["lease_until"] is None
    assert "schedule_snapshot_setup_failed" in eps["last_error"]
    assert db.fetchone("SELECT COUNT(*) AS c FROM distribution_targets")['c'] == 0
