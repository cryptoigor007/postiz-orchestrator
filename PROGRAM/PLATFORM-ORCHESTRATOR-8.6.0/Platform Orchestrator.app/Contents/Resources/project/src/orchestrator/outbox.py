"""Durable transactional outbox for scheduling side effects after DB commit."""
from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Outbox:
    def __init__(self, db: Any) -> None:
        self.db = db

    def enqueue_in_transaction(self, conn: Any, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict[str, Any]) -> int:
        """Insert an outbox row using an existing transaction connection."""
        now = _now()
        cur = conn.execute(
            "INSERT INTO outbox_events(event_type, aggregate_type, aggregate_id, payload_json, created_at, status) "
            "VALUES (?, ?, ?, ?, ?, 'pending')",
            (event_type, aggregate_type, aggregate_id, json.dumps(payload, ensure_ascii=False, sort_keys=True), now),
        )
        return int(cur.lastrowid or 0)

    def enqueue(self, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict[str, Any]) -> int:
        with self.db.transaction() as conn:
            return self.enqueue_in_transaction(conn, event_type, aggregate_type, aggregate_id, payload)

    def claim(self, limit: int = 50, lease_sec: int = 60, *, max_attempts: int = 12) -> list[dict[str, Any]]:
        now = _now()
        until = (datetime.now(UTC) + timedelta(seconds=lease_sec)).isoformat()
        max_attempts = max(1, int(max_attempts))
        rows = self.db.fetchall(
            "SELECT * FROM outbox_events WHERE status='pending' "
            "AND (locked_until IS NULL OR locked_until < ?) "
            "AND attempts < ? ORDER BY id LIMIT ?",
            (now, max_attempts, max(1, int(limit))),
        )
        claimed: list[dict[str, Any]] = []
        for row in rows:
            updated = self.db.execute(
                "UPDATE outbox_events SET locked_until=?, attempts=attempts+1 "
                "WHERE id=? AND status='pending' "
                "AND (locked_until IS NULL OR locked_until < ?) "
                "AND attempts < ?",
                (until, row["id"], now, max_attempts),
            )
            if updated:
                claimed.append(dict(row))
        return claimed

    def mark_published(self, event_id: int) -> None:
        self.db.execute(
            "UPDATE outbox_events SET status='published', published_at=?, locked_until=NULL, last_error=NULL WHERE id=?",
            (_now(), int(event_id)),
        )

    def mark_failed(self, event_id: int, error: str, *, max_attempts: int = 12) -> None:
        row = self.db.fetchone("SELECT attempts, status FROM outbox_events WHERE id=?", (int(event_id),))
        attempts = int(row.get("attempts") or 0) if row else 0
        if attempts >= max(1, int(max_attempts)):
            self.db.execute(
                "UPDATE outbox_events SET status='dead', locked_until=NULL, last_error=? WHERE id=?",
                (str(error)[:1000], int(event_id)),
            )
        else:
            self.db.execute(
                "UPDATE outbox_events SET status='pending', locked_until=NULL, last_error=? WHERE id=?",
                (str(error)[:1000], int(event_id)),
            )

    def replay(self, event_id: int) -> bool:
        """Return a dead event to the pending queue for an explicit operator replay."""
        return bool(self.db.execute(
            "UPDATE outbox_events SET status='pending', published_at=NULL, locked_until=NULL, "
            "attempts=0, last_error=NULL WHERE id=? AND status='dead'",
            (int(event_id),),
        ))

    def dead(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.fetchall(
            "SELECT * FROM outbox_events WHERE status='dead' ORDER BY id DESC LIMIT ?",
            (max(1, int(limit)),),
        )


class DurableJobStore:
    """SQLite-backed restart-safe jobs with leases, retries and a durable DLQ."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        provider: str = "",
        account_id: str = "",
        job_id: str | None = None,
        available_at: str | None = None,
        max_attempts: int = 8,
    ) -> str:
        jid = job_id or secrets.token_urlsafe(16)
        now = _now()
        self.db.execute(
            "INSERT INTO durable_jobs(id, kind, provider, account_id, payload_json, available_at, "
            "created_at, updated_at, max_attempts, next_retry_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL) "
            "ON CONFLICT(id) DO NOTHING",
            (jid, kind, provider, account_id, json.dumps(payload, ensure_ascii=False, sort_keys=True),
             available_at or now, now, now, max(1, int(max_attempts))),
        )
        return jid

    def reap_expired(self, *, now: str | None = None) -> dict[str, int]:
        now = now or _now()
        rows = self.db.fetchall(
            "SELECT id, attempts, max_attempts FROM durable_jobs "
            "WHERE status='running' AND locked_until IS NOT NULL AND locked_until<?", (now,)
        )
        requeued = dead = 0
        for row in rows:
            attempts = int(row.get("attempts") or 0)
            limit = max(1, int(row.get("max_attempts") or 8))
            if attempts >= limit:
                self.dead_letter(str(row["id"]), "worker lease expired; max attempts reached")
                dead += 1
            else:
                delay = min(3600, 2 ** min(attempts, 10))
                available = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
                self.retry(str(row["id"]), "worker lease expired", available_at=available)
                requeued += 1
        return {"requeued": requeued, "dead": dead}

    def claim(self, worker_id: str, *, limit: int = 10, lease_sec: int = 300) -> list[dict[str, Any]]:
        now = _now()
        self.reap_expired(now=now)
        until = (datetime.now(UTC) + timedelta(seconds=lease_sec)).isoformat()
        rows = self.db.fetchall(
            "SELECT * FROM durable_jobs WHERE status='queued' AND available_at<=? "
            "AND (next_retry_at IS NULL OR next_retry_at<=?) "
            "AND (locked_until IS NULL OR locked_until<?) "
            "AND attempts < COALESCE(max_attempts,8) ORDER BY available_at, created_at LIMIT ?",
            (now, now, now, max(1, int(limit))),
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            n = self.db.execute(
                "UPDATE durable_jobs SET status='running', locked_until=?, worker_id=?, "
                "attempts=attempts+1, updated_at=?, next_retry_at=NULL WHERE id=? AND status='queued' "
                "AND (locked_until IS NULL OR locked_until<?) AND attempts < COALESCE(max_attempts,8)",
                (until, worker_id, now, row["id"], now),
            )
            if n:
                row = dict(row)
                row["attempts"] = int(row.get("attempts") or 0) + 1
                out.append(row)
        return out

    def heartbeat(self, job_id: str, worker_id: str, *, lease_sec: int = 300) -> bool:
        now = _now()
        until = (datetime.now(UTC) + timedelta(seconds=lease_sec)).isoformat()
        return bool(self.db.execute(
            "UPDATE durable_jobs SET locked_until=?, updated_at=? "
            "WHERE id=? AND status='running' AND worker_id=?",
            (until, now, job_id, worker_id),
        ))

    def complete(self, job_id: str) -> None:
        now = _now()
        self.db.execute(
            "UPDATE durable_jobs SET status='done', locked_until=NULL, worker_id=NULL, "
            "finished_at=?, updated_at=? WHERE id=?",
            (now, now, job_id),
        )

    def retry(self, job_id: str, error: str, *, available_at: str | None = None) -> None:
        now = _now()
        self.db.execute(
            "UPDATE durable_jobs SET status='queued', locked_until=NULL, worker_id=NULL, "
            "available_at=?, next_retry_at=?, last_error=?, updated_at=? WHERE id=?",
            (available_at or now, available_at or now, str(error)[:1000], now, job_id),
        )

    def fail_or_retry(self, job_id: str, error: str) -> str:
        row = self.db.fetchone("SELECT attempts, max_attempts FROM durable_jobs WHERE id=?", (job_id,))
        attempts = int(row.get("attempts") or 0) if row else 0
        limit = max(1, int(row.get("max_attempts") or 8)) if row else 8
        if attempts >= limit:
            self.dead_letter(job_id, error)
            return "dead"
        delay = min(3600, 2 ** min(attempts, 10))
        when = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
        self.retry(job_id, error, available_at=when)
        return "retry"

    def dead_letter(self, job_id: str, error: str) -> None:
        now = _now()
        self.db.execute(
            "UPDATE durable_jobs SET status='dead', locked_until=NULL, worker_id=NULL, "
            "last_error=?, finished_at=?, updated_at=? WHERE id=?",
            (str(error)[:1000], now, now, job_id),
        )

