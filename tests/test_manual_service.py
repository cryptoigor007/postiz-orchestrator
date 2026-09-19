from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.manual_uploads import ManualUploadsService

ROOT = Path(__file__).resolve().parents[1]


def make(tmp_path):
    db = Database(tmp_path / "m.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    clock = FakeClock(datetime(2026, 9, 19, 12, 0, tzinfo=UTC))
    return ManualUploadsService(db, cfg, clock), db, clock


def test_scan_marks_origin_and_suggests(tmp_path):
    svc, db, clock = make(tmp_path)
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('videomaker','/s1','S1','/s1/w.mp4','Серия 1 Победа',?)",
        (now,),
    )
    # known postiz id -> must be classified as postiz
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, postiz_post_id) "
        "VALUES ('long_video', 999, 'youtube', 'scheduled', 'KNOWN1')"
    )
    uploads = [
        {"external_id": "KNOWN1", "title": "x", "published_at": now},
        {"external_id": "MAN1", "title": "Серия 1 Победа",
         "published_at": "2026-09-19T11:00:00+00:00", "duration_sec": 120},
    ]
    stats = svc.scan("youtube", uploads)
    assert stats["found"] == 2
    assert stats["postiz"] == 1
    assert stats["manual"] == 1
    rows = db.list_uploads()
    manual = [r for r in rows if r["platform_video_id"] == "MAN1"][0]
    assert manual["origin"] == "manual"
    assert manual["match_status"] == "suggested"
    assert manual["confidence"] and manual["confidence"] > 0.5
    postiz_row = [r for r in rows if r["platform_video_id"] == "KNOWN1"][0]
    assert postiz_row["origin"] == "postiz"


def test_confirm_applies_published_and_is_idempotent(tmp_path):
    svc, db, clock = make(tmp_path)
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('videomaker','/s2','S2','/s2/w.mp4','Серия 2',?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/s2'")["id"]
    up = db.upsert_upload(engine="direct", platform="youtube", external_id="V1",
                          url="https://youtu.be/V1", title="Серия 2", origin="manual")
    db.set_upload_match(up["id"], "long_video", vid, 0.9, "suggested")

    assert svc.confirm(up["id"], "long_video", vid, confidence=0.9) is True
    row = db.get_upload(up["id"])
    assert row["match_status"] == "confirmed"
    eps = db.fetchone(
        "SELECT status, release_url FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='youtube'",
        (vid,),
    )
    assert eps["status"] == "published"
    assert eps["release_url"] == "https://youtu.be/V1"

    # idempotent
    assert svc.confirm(up["id"], "long_video", vid, confidence=1.0) is True
    assert len(db.list_uploads(status="confirmed")) == 1


def test_reject_and_candidates(tmp_path):
    svc, db, clock = make(tmp_path)
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('videomaker','/s3','S3','/s3/w.mp4','Серия 3',?)",
        (now,),
    )
    up = db.upsert_upload(engine="direct", platform="youtube", external_id="V2",
                          title="Серия 3", published_at=now, origin="manual")
    cands = svc.candidates(up["id"])
    assert cands and cands[0]["entity_type"] == "long_video"
    svc.reject(up["id"])
    assert db.get_upload(up["id"])["match_status"] == "rejected"


class _ListSource:
    def __init__(self, uploads): self.uploads = uploads
    def capabilities(self): return {"list": True}
    def list_uploads(self, params=None): return self.uploads


class _NoList:
    def capabilities(self): return {"list": False}


class _Boom:
    def capabilities(self): return {"list": True}
    def list_uploads(self, params=None): raise RuntimeError("net down")


def test_scan_all_handles_mixed_sources(tmp_path):
    svc, db, clock = make(tmp_path)
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('videomaker','/sa','SA','/sa/w.mp4','Серия SA',?)", (now,))
    sources = {
        "youtube": _ListSource([{"external_id": "Y1", "title": "Серия SA",
                                 "published_at": "2026-09-19T11:00:00+00:00"}]),
        "telegram": _NoList(),
        "x": _Boom(),
    }
    stats = svc.scan_all(sources)
    assert stats["youtube"]["manual"] == 1
    assert stats["telegram"]["skipped"]
    assert "net down" in stats["x"]["error"]


def test_runner_manual_cycle(tmp_path):
    from orchestrator.runner import Runner
    svc, db, clock = make(tmp_path)
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('videomaker','/rc','RC','/rc/w.mp4','Серия RC',?)", (now,))
    comps = {
        "cfg": svc.cfg, "db": db, "clock": clock, "manual": svc,
        "manual_sources": {"youtube": _ListSource([
            {"external_id": "RC1", "title": "Серия RC",
             "published_at": "2026-09-19T11:00:00+00:00"}])},
    }
    r = Runner(comps, dry_run=True, health_port=0)
    r._cycle_manual()
    import json as _json
    saved = _json.loads(db.get_setting("manual_last_scan"))
    assert saved["stats"]["youtube"]["manual"] == 1


def test_scan_honors_lookback(tmp_path):
    svc, db, clock = make(tmp_path)
    svc.cfg.manual_uploads.lookback_days = 10
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('v','/lb','LB','/lb/w.mp4','Серия LB',?)", (now,))
    uploads = [
        {"external_id": "OLD", "title": "Серия LB", "published_at": "2026-01-01T00:00:00+00:00"},
        {"external_id": "NEW", "title": "Серия LB", "published_at": "2026-09-18T00:00:00+00:00"},
    ]
    stats = svc.scan("youtube", uploads)
    assert stats["found"] == 1
    ids = [u["platform_video_id"] for u in db.list_uploads()]
    assert ids == ["NEW"]


class _RecordingEngine:
    def __init__(self): self.calls = []
    def update_metadata(self, external_id, data):
        self.calls.append((external_id, data))
        return True


def test_scan_all_respects_platforms_filter(tmp_path):
    svc, db, clock = make(tmp_path)
    svc.cfg.manual_uploads.platforms = ["youtube"]
    sources = {
        "youtube": _ListSource([{"external_id": "Y9", "title": "x", "published_at": None}]),
        "telegram": _ListSource([{"external_id": "T9", "title": "y", "published_at": None}]),
    }
    stats = svc.scan_all(sources)
    assert "youtube" in stats and "telegram" not in stats


def test_confirm_blocks_edits_on_claim(tmp_path):
    svc, db, clock = make(tmp_path)
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, created_at) "
        "VALUES ('v','/cl','CL','/cl/w.mp4','Серия CL',?)", (now,))
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/cl'")["id"]
    up = db.upsert_upload(engine="direct", platform="youtube", external_id="CL1",
                          url="https://youtu.be/CL1", title="Серия CL", origin="manual")
    db.execute("UPDATE platform_uploads SET claim_status='claimed' WHERE id=?", (up["id"],))
    eng = _RecordingEngine()
    svc.confirm(up["id"], "long_video", vid, apply_edits=True, engine=eng)
    assert eng.calls == []  # edits blocked by claim
    assert db.get_upload(up["id"])["edit_error"] == "blocked: claim"
