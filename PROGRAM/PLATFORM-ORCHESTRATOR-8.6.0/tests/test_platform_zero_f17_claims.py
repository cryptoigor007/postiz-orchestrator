
"""F17 claims job mock."""
from __future__ import annotations
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from orchestrator.clock import FakeClock
from orchestrator.db import Database
from orchestrator.claims import run_claims_check, a3_delete_and_next

class _YT:
    def check_claims(self, eid):
        return SimpleNamespace(supported=True, has_claim=(eid == "CLAIMED1"))
    def delete(self, eid):
        return True

def test_claims_detects_claimed(tmp_path):
    db = Database(tmp_path / "c.sqlite")
    clock = FakeClock(datetime(2026, 5, 1, 12, 0, tzinfo=UTC))
    slot = (clock.now() + timedelta(hours=3)).isoformat()
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, external_id, scheduled_for) "
        "VALUES ('long_video', 1, 'youtube', 'scheduled', 'CLAIMED1', ?)",
        (slot,),
    )
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, external_id, scheduled_for) "
        "VALUES ('long_video', 2, 'youtube', 'scheduled', 'CLEAN1', ?)",
        (slot,),
    )
    r = run_claims_check(db, clock=clock, youtube_module=_YT(), hours_before=6)
    assert r.checked == 2
    assert r.claimed == 1
    assert r.clean == 1

def test_a3_flow(tmp_path):
    db = Database(tmp_path / "a3.sqlite")
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, external_id) "
        "VALUES ('long_video', 9, 'youtube', 'scheduled', 'X')"
    )
    assert a3_delete_and_next(db, publisher=None, entity_type="long_video", entity_id=9, platform="youtube", youtube_module=_YT())
    row = db.fetchone("SELECT status, external_id FROM entity_platform_status WHERE entity_id=9")
    assert row["status"] == "claimed_skipped"
    assert not row["external_id"]
