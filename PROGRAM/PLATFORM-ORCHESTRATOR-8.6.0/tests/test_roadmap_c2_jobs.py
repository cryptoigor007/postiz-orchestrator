from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

from orchestrator.db import Database
from orchestrator.outbox import DurableJobStore


def test_durable_job_lease_requeues_and_can_dead_letter(tmp_path):
    db = Database(tmp_path / "jobs.sqlite")
    jobs = DurableJobStore(db)
    jid = jobs.enqueue("x", {"a": 1}, job_id="j1", max_attempts=2)
    claimed = jobs.claim("w1", lease_sec=1)
    assert [j["id"] for j in claimed] == [jid]
    db.execute("UPDATE durable_jobs SET locked_until=? WHERE id=?", ((datetime.now(UTC) - timedelta(seconds=5)).isoformat(), jid))
    result = jobs.reap_expired()
    assert result["requeued"] == 1
    assert db.fetchone("SELECT status FROM durable_jobs WHERE id=?", (jid,))["status"] == "queued"

    db.execute("UPDATE durable_jobs SET status='running', worker_id='w1', attempts=2, locked_until=? WHERE id=?", ((datetime.now(UTC) - timedelta(seconds=5)).isoformat(), jid))
    result = jobs.reap_expired()
    assert result["dead"] == 1
    assert db.fetchone("SELECT status FROM durable_jobs WHERE id=?", (jid,))["status"] == "dead"


def test_durable_job_heartbeat_requires_owner(tmp_path):
    db = Database(tmp_path / "hb.sqlite")
    jobs = DurableJobStore(db)
    jobs.enqueue("x", {}, job_id="j1")
    jobs.claim("owner", lease_sec=60)
    assert jobs.heartbeat("j1", "wrong") is False
    assert jobs.heartbeat("j1", "owner") is True
