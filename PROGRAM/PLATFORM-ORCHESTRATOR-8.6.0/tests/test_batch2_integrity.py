from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from orchestrator.claims import run_claims_check
from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler_recovery import SchedulerRecovery


class _YT:
    def check_claims(self, eid):
        from types import SimpleNamespace
        return SimpleNamespace(supported=True, has_claim=(eid == "A"))


def test_claims_is_account_scoped(tmp_path):
    db = Database(tmp_path / "claims.sqlite")
    clock = FakeClock(datetime(2026, 10, 2, 12, tzinfo=UTC))
    slot = (clock.now() + timedelta(hours=1)).isoformat()
    for eid, account, external in [(1, "a1", "A"), (2, "a2", "A")]:
        db.execute(
            "INSERT INTO entity_platform_status "
            "(entity_type, entity_id, platform, account_id, status, external_id, scheduled_for) "
            "VALUES ('long_video', ?, 'youtube', ?, 'scheduled', ?, ?)",
            (eid, account, external, slot),
        )
    result = run_claims_check(db, clock=clock, youtube_module=_YT(), hours_before=6, account_id="a1")
    assert result.checked == 1
    assert db.fetchone("SELECT claims_state FROM entity_platform_status WHERE entity_id=1")['claims_state'] == 'claimed'
    assert db.fetchone("SELECT claims_state FROM entity_platform_status WHERE entity_id=2")['claims_state'] in (None, '')


def test_idempotency_uses_content_hash_not_mtime(tmp_path):
    cfg = load_config("config.ci.yaml")
    db = Database(tmp_path / "pub.sqlite")
    clock = FakeClock(datetime(2026, 10, 2, 12, tzinfo=UTC))
    pub = Publisher(db, cfg, SafetyChecker(db, cfg, clock), clock, dry_run=True)
    media = Path(tmp_path) / "clip.bin"
    media.write_bytes(b"same-bytes")
    key1 = pub._idempotency_key("short", 1, "youtube", "a1", str(media), {"title": "x"})
    media.touch()
    key2 = pub._idempotency_key("short", 1, "youtube", "a1", str(media), {"title": "x"})
    assert key1 == key2
    media.write_bytes(b"different-bytes")
    assert pub._idempotency_key("short", 1, "youtube", "a1", str(media), {"title": "x"}) != key1


def test_local_schedule_requires_snapshot_and_lease(tmp_path):
    db = Database(tmp_path / "schedule.sqlite")
    clock = FakeClock(datetime(2026, 10, 2, 12, tzinfo=UTC))
    recovery = SchedulerRecovery(db, clock)
    slot = (clock.now() - timedelta(minutes=1)).isoformat()
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, account_id, status, external_id, publish_mode, scheduled_for) "
        "VALUES ('short', 1, 'youtube', 'a1', 'ready', 'local-youtube-short-1', 'local_schedule', ?)",
        (slot,),
    )
    rows = recovery.claim_due_local()
    assert len(rows) == 1
    state = db.fetchone("SELECT status, external_id, lease_until FROM entity_platform_status WHERE entity_id=1")
    assert state['status'] == 'publishing'
    assert state['external_id'] is None
    assert state['lease_until']
