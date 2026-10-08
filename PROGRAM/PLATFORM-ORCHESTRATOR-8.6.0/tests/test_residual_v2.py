from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.scheduler_recovery import SchedulerRecovery

ROOT = Path(__file__).resolve().parents[1]

def test_next_retry_future_is_not_claimed(tmp_path):
    db = Database(tmp_path / "retry.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    clock = FakeClock(datetime(2026, 10, 2, 10, 0, tzinfo=UTC))
    db.execute("INSERT INTO shorts(source,folder_path,title_text,created_at) VALUES('x','/x','x',?)", (clock.now().isoformat(),))
    sid = db.fetchone("SELECT id FROM shorts ORDER BY id DESC LIMIT 1")["id"]
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,scheduled_for,next_retry_at,publish_mode) VALUES('short',?,?,?,?,?,?,?)", (sid,'youtube','acct','scheduled',clock.now().isoformat(),(clock.now()+timedelta(seconds=30)).isoformat(),'local_schedule'))
    rec = SchedulerRecovery(db, clock)
    assert rec.claim_due_local() == []
    clock.advance(seconds=31)
    assert len(rec.claim_due_local()) == 1
