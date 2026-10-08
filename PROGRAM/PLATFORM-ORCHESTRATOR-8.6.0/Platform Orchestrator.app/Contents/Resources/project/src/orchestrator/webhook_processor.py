from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WebhookProcessResult:
    checked: int = 0
    processed: int = 0
    retried: int = 0
    dead: int = 0
    repaired: int = 0


class WebhookEventProcessor:
    """Durable webhook normalizer/processor with replay-safe claiming and DLQ."""

    def __init__(self, db: Any, *, max_attempts: int = 8):
        self.db = db
        self.max_attempts = max(1, int(max_attempts))

    def claim(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM webhook_events WHERE signature_valid=1 AND processed_at IS NULL "
            "AND processing_state IN ('queued','retry') ORDER BY received_at LIMIT ?", (max(1, int(limit)),)
        )
        out=[]
        for row in rows:
            n=self.db.execute(
                "UPDATE webhook_events SET processing_state='processing', attempts=attempts+1 WHERE id=? "
                "AND processed_at IS NULL AND processing_state IN ('queued','retry')", (row['id'],)
            )
            if n:
                out.append(row)
        return out

    def run(self, *, limit: int = 50) -> WebhookProcessResult:
        res=WebhookProcessResult()
        for row in self.claim(limit):
            res.checked += 1
            try:
                payload=json.loads(row.get('payload_json') or '{}')
                event_type, external_id, new_status = self.normalize(str(row['provider']), payload)
                if not external_id:
                    raise ValueError(f"unsupported {row['provider']} webhook: missing external_id")
                self.db.execute(
                    "UPDATE webhook_events SET normalized_type=?, external_id=?, processing_state='done', processed_at=datetime('now'), processed_result=? WHERE id=?",
                    (event_type, external_id, json.dumps({'status':new_status}, ensure_ascii=False), row['id']),
                )
                if external_id:
                    res.repaired += self._repair_eps(str(row['provider']), str(row.get('account_id') or ''), external_id, new_status)
                res.processed += 1
            except Exception as exc:
                attempts=int(row.get('attempts') or 1)
                if attempts >= self.max_attempts:
                    self.db.execute("UPDATE webhook_events SET processing_state='dead', last_error=? WHERE id=?", (str(exc)[:1000], row['id']))
                    res.dead += 1
                else:
                    self.db.execute("UPDATE webhook_events SET processing_state='retry', last_error=? WHERE id=?", (str(exc)[:1000], row['id']))
                    res.retried += 1
        return res

    def replay(self, event_id: int) -> bool:
        row=self.db.fetchone("SELECT id FROM webhook_events WHERE id=?", (int(event_id),))
        if not row:
            return False
        return bool(self.db.execute("UPDATE webhook_events SET processed_at=NULL, processing_state='retry', last_error=NULL WHERE id=?", (int(event_id),)))

    @staticmethod
    def normalize(provider: str, payload: dict[str, Any]) -> tuple[str, str, str]:
        if not isinstance(payload, dict):
            raise ValueError("webhook payload must be an object")
        provider = str(provider or "").lower().strip()
        event_type = str(payload.get("type") or payload.get("event") or payload.get("object") or "").strip()
        external_id = str(payload.get("external_id") or payload.get("id") or payload.get("publish_id") or "").strip()
        status = str(payload.get("status") or payload.get("state") or "").strip().lower()
        data = payload.get("data")
        if isinstance(data, dict):
            event_type = str(data.get("event") or data.get("type") or event_type).strip()
            external_id = str(data.get("id") or data.get("external_id") or data.get("publish_id") or external_id).strip()
            status = str(data.get("status") or data.get("state") or status).strip().lower()
        # Meta often wraps one logical event under entry[].changes[].value.
        entries = payload.get("entry")
        if isinstance(entries, list) and entries and isinstance(entries[0], dict):
            entry = entries[0]
            external_id = external_id or str(entry.get("id") or "").strip()
            changes = entry.get("changes")
            if isinstance(changes, list) and changes and isinstance(changes[0], dict):
                value = changes[0].get("value")
                if isinstance(value, dict):
                    event_type = str(changes[0].get("field") or value.get("event") or event_type).strip()
                    external_id = external_id or str(value.get("id") or value.get("media_id") or value.get("message_id") or "").strip()
                    status = str(value.get("status") or value.get("state") or status).strip().lower()
        if not event_type:
            raise ValueError(f"unsupported {provider} webhook: missing event/type")
        if status and not external_id:
            raise ValueError(f"unsupported {provider} webhook: status without external_id")
        return event_type, external_id, status

    def _repair_eps(self, provider: str, account_id: str, external_id: str, status: str) -> int:
        mapping={'published':'published','failed':'error','deleted':'error','processing':'processing','scheduled':'scheduled'}
        local=mapping.get(status, '')
        if not local:
            return 0
        return self.db.execute(
            "UPDATE entity_platform_status SET status=?, last_status_sync_at=datetime('now'), last_error=CASE WHEN ?='error' THEN last_error ELSE NULL END "
            "WHERE platform=? AND account_id=? AND external_id=?", (local, local, provider, account_id, external_id)
        )

    def reconcile_subscriptions(self, *, stale_after_sec: int = 3600) -> int:
        cutoff = (datetime.now(UTC).timestamp() - max(60, int(stale_after_sec)))
        rows = self.db.fetchall("SELECT provider, account_id, last_checked_at, desired, verified FROM webhook_subscriptions WHERE desired=1")
        changed = 0
        for row in rows or []:
            raw = str(row.get("last_checked_at") or "")
            try:
                ts = datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp() if raw else 0
            except Exception:
                ts = 0
            if ts < cutoff and int(row.get("verified") or 0):
                self.db.execute(
                    "UPDATE webhook_subscriptions SET verified=0, last_error='subscription verification stale', last_checked_at=datetime('now') WHERE provider=? AND account_id=?",
                    (row.get("provider"), row.get("account_id") or ""),
                )
                changed += 1
        return changed

    def set_subscription(self, provider: str, account_id: str, endpoint: str, *, desired: bool = True, verified: bool = False, error: str = "") -> None:
        self.db.execute(
            "INSERT INTO webhook_subscriptions(provider,account_id,endpoint,desired,verified,last_checked_at,last_error) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(provider,account_id) DO UPDATE SET endpoint=excluded.endpoint,desired=excluded.desired,verified=excluded.verified,last_checked_at=excluded.last_checked_at,last_error=excluded.last_error",
            (provider, account_id, endpoint, int(desired), int(verified), datetime.now(UTC).isoformat(), error[:1000]),
        )
