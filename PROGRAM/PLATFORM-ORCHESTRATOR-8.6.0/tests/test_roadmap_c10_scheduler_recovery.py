from __future__ import annotations
from datetime import UTC, datetime, timedelta
from orchestrator.db import Database
from orchestrator.clock import FakeClock
from orchestrator.scheduler_recovery import SchedulerRecovery


def test_due_local_claim_is_account_aware(tmp_path):
    clock=FakeClock(datetime(2026,10,1,12,0,tzinfo=UTC)); db=Database(tmp_path/'s.sqlite')
    for aid in ('a','b'):
        db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,external_id,publish_mode,scheduled_for,lease_until) VALUES('short',1,'x',?,'scheduled','local-x','local_schedule',?,NULL)",(aid,(clock.now()-timedelta(minutes=1)).isoformat()))
    claimed=SchedulerRecovery(db,clock).claim_due_local()
    assert len(claimed)==2
    assert {r['account_id'] for r in claimed}=={'a','b'}
    assert all(r['status']=='scheduled' for r in claimed)
    assert {r['external_id'] for r in db.fetchall("SELECT * FROM entity_platform_status WHERE platform='x'")}=={None}


def test_stale_publish_lease_recovers(tmp_path):
    clock=FakeClock(datetime(2026,10,1,12,0,tzinfo=UTC)); db=Database(tmp_path/'s2.sqlite')
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,lease_until) VALUES('short',1,'x','a','publishing',?)",((clock.now()-timedelta(minutes=10)).isoformat(),))
    assert SchedulerRecovery(db,clock).recover_stale_leases()==1
    row=db.fetchone("SELECT status,last_error FROM entity_platform_status WHERE entity_type='short' AND entity_id=1 AND platform='x' AND account_id='a'")
    assert row['status']=='ready'
    assert row['last_error']=='recovered_stale_publish_lease'


def test_due_local_claim_respects_next_retry_at(tmp_path):
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    clock = FakeClock(now)
    db = Database(tmp_path / 'retry.sqlite')
    db.execute(
        "INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,external_id,publish_mode,scheduled_for,next_retry_at) "
        "VALUES('short',1,'x','a','ready','local-x','local_schedule',?,?)",
        ((now - timedelta(minutes=1)).isoformat(), (now + timedelta(seconds=30)).isoformat()),
    )
    assert SchedulerRecovery(db, clock).claim_due_local() == []
    clock.advance(seconds=31)
    claimed = SchedulerRecovery(db, clock).claim_due_local()
    assert len(claimed) == 1
    assert claimed[0]['account_id'] == 'a'


def test_stale_publish_lease_recovery_is_account_scoped(tmp_path):
    clock = FakeClock(datetime(2026,10,1,12,0,tzinfo=UTC)); db = Database(tmp_path/'s3.sqlite')
    old = (clock.now()-timedelta(minutes=10)).isoformat()
    for aid in ('a','b'):
        db.execute(
            "INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,lease_until) "
            "VALUES('short',1,'x',?,'publishing',?)", (aid, old),
        )
    # Both are stale and both may recover, but never through a cross-account UPDATE.
    assert SchedulerRecovery(db, clock).recover_stale_leases() == 2
    rows = db.fetchall("SELECT account_id,status,last_error FROM entity_platform_status WHERE platform='x' ORDER BY account_id")
    assert [(r['account_id'], r['status']) for r in rows] == [('a','ready'),('b','ready')]
