from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


class SchedulerRecovery:
    """Restart/DST safe scheduling primitives over account-aware EPS."""

    def __init__(self, db: Any, clock: Any):
        self.db = db
        self.clock = clock

    def recover_stale_leases(self, *, lease_grace_sec: int = 60) -> int:
        now = self.clock.now()
        cutoff = (now - timedelta(seconds=max(0, int(lease_grace_sec)))).isoformat()
        rows = self.db.fetchall(
            "SELECT entity_type, entity_id, platform, account_id FROM entity_platform_status "
            "WHERE status='publishing' AND lease_until IS NOT NULL AND lease_until<?",
            (cutoff,),
        )
        recovered = 0
        for row in rows or []:
            recovered += self.db.execute(
                "UPDATE entity_platform_status SET status='ready', lease_until=NULL, "
                "last_error='recovered_stale_publish_lease', next_retry_at=? "
                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? "
                "AND status='publishing' AND lease_until IS NOT NULL AND lease_until<?",
                (now.isoformat(), row["entity_type"], row["entity_id"], row["platform"], str(row.get("account_id") or ""), cutoff),
            ) or 0
        return recovered

    def claim_due_local(self, limit: int = 50) -> list[dict[str, Any]]:
        now = self.clock.now().isoformat()
        rows = self.db.fetchall(
            "SELECT entity_type,entity_id,platform,account_id,external_id,publish_mode,status,scheduled_for FROM entity_platform_status "
            "WHERE status IN ('scheduled','ready') AND scheduled_for IS NOT NULL AND scheduled_for<=? "
            "AND (next_retry_at IS NULL OR next_retry_at<=?) "
            "AND (publish_mode='local_schedule' OR external_id LIKE 'local-%') ORDER BY scheduled_for LIMIT ?",
            (now, now, max(1, int(limit))),
        )
        claimed=[]
        lease=(self.clock.now()+timedelta(minutes=5)).isoformat()
        for row in rows:
            ok=self.db.execute(
                "UPDATE entity_platform_status SET status='publishing', external_id=NULL, lease_until=?, attempt=COALESCE(attempt,0)+1 "
                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? AND status IN ('scheduled','ready')",
                (lease,row['entity_type'],row['entity_id'],row['platform'],row.get('account_id') or ''),
            )
            if ok:
                r=dict(row); r['account_id']=str(row.get('account_id') or ''); claimed.append(r)
        return claimed
