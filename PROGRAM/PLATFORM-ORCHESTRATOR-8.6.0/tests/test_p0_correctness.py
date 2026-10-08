from __future__ import annotations

from datetime import UTC, datetime, timedelta

from orchestrator.db import Database
from orchestrator.outbox import DurableJobStore, Outbox
from orchestrator.runner import Runner


class _Metrics:
    def __init__(self):
        self.values = {}

    def incr(self, key: str, value: int = 1):
        self.values[key] = self.values.get(key, 0) + value


def test_durable_unknown_handler_never_completes(tmp_path):
    db = Database(tmp_path / "jobs.sqlite")
    jobs = DurableJobStore(db)
    jid = jobs.enqueue("does.not.exist", {"x": 1}, job_id="unknown-1", max_attempts=2)
    runner = object.__new__(Runner)
    runner.comps = {"durable_jobs": jobs, "job_handlers": {}}
    runner.metrics = _Metrics()

    runner._cycle_durable_jobs("test-worker")

    row = db.fetchone("SELECT status, last_error, attempts FROM durable_jobs WHERE id=?", (jid,))
    assert row["status"] == "queued"
    assert "no handler for kind=does.not.exist" in row["last_error"]
    assert row["attempts"] == 1
    assert runner.metrics.values["durable_jobs_retry"] == 1


def test_outbox_dead_letter_is_not_reclaimed(tmp_path):
    db = Database(tmp_path / "outbox.sqlite")
    outbox = Outbox(db)
    eid = outbox.enqueue("evt", "test", "1", {"ok": True})

    claimed = outbox.claim(max_attempts=1)
    assert [row["id"] for row in claimed] == [eid]
    outbox.mark_failed(eid, "boom", max_attempts=1)

    row = db.fetchone("SELECT status, published_at, last_error FROM outbox_events WHERE id=?", (eid,))
    assert row["status"] == "dead"
    assert row["published_at"] is None
    assert row["last_error"] == "boom"
    assert outbox.claim(max_attempts=1) == []
    assert [row["id"] for row in outbox.dead()] == [eid]
    assert outbox.replay(eid) is True
    assert outbox.claim(max_attempts=1)[0]["id"] == eid


def test_outbox_claim_respects_max_attempts(tmp_path):
    db = Database(tmp_path / "outbox_attempts.sqlite")
    outbox = Outbox(db)
    eid = outbox.enqueue("evt", "test", "2", {"ok": True})
    db.execute("UPDATE outbox_events SET attempts=3 WHERE id=?", (eid,))

    assert outbox.claim(max_attempts=3) == []
    assert db.fetchone("SELECT status FROM outbox_events WHERE id=?", (eid,))["status"] == "pending"


def test_deploy_excludes_tokens_from_delete_sync():
    text = (
        __import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "deploy.sh"
    ).read_text(encoding="utf-8")
    assert "--exclude tokens" in text
    assert "<PVE_TAILSCALE_HOST>" not in text
    assert "<ORCH_HOST_IP>" not in text
    assert "<PVE_LAN_HOST>" not in text
