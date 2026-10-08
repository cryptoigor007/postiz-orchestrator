from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .platforms.base import NotSupported

logger = logging.getLogger(__name__)


@dataclass
class RecoveryResult:
    checked: int = 0
    repaired: int = 0
    ambiguous: int = 0
    failed: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


class PublishAttemptRecovery:
    """Repair publish attempts after lost responses without inventing a remote ID."""

    def __init__(self, db: Any, module_registry: Any, cfg: Any = None, *, clock: Any = None):
        self.db = db
        self.registry = module_registry
        self.cfg = cfg
        self.clock = clock

    def run(self, *, limit: int = 50) -> RecoveryResult:
        res = RecoveryResult()
        rows = self.db.fetchall(
            "SELECT * FROM publish_attempts WHERE status IN ('started','unknown','processing') "
            "ORDER BY started_at LIMIT ?",
            (max(1, int(limit)),),
        )
        for row in rows:
            res.checked += 1
            try:
                outcome = self._repair_one(row)
                if outcome == "repaired":
                    res.repaired += 1
                elif outcome == "ambiguous":
                    res.ambiguous += 1
                elif outcome == "failed":
                    res.failed += 1
            except Exception as exc:
                res.failed += 1
                res.errors.append(f"{row.get('id')}: {type(exc).__name__}: {exc}")
        return res

    def _module(self, platform: str, account_id: str):
        if self.registry is None or not self.registry.has(platform):
            return None
        from .auth_tokens import token_provider_for
        return self.registry.create(
            platform,
            cfg=self.cfg,
            token_provider=token_provider_for(platform),
            account_id=account_id,
        )

    def _repair_one(self, row: dict[str, Any]) -> str:
        platform = str(row.get("platform") or "")
        account_id = str(row.get("account_id") or "")
        mod = self._module(platform, account_id)
        if mod is None:
            return "unresolved"

        remote_id = str(row.get("remote_object_id") or "").strip()
        if not remote_id:
            eps = self.db.fetchone(
                "SELECT external_id FROM entity_platform_status WHERE entity_type=? AND entity_id=? "
                "AND platform=? AND account_id=?",
                (row["entity_type"], row["entity_id"], platform, account_id),
            )
            remote_id = str((eps or {}).get("external_id") or "").strip()
        if remote_id:
            try:
                status = mod.get_status(remote_id)
            except NotSupported:
                status = None
            if status is not None:
                state = str(getattr(status, "state", "unknown") or "unknown")
                self.db.execute(
                    "UPDATE publish_attempts SET status=?, remote_object_id=?, finished_at=CASE "
                    "WHEN ? IN ('published','completed') THEN COALESCE(finished_at, ?) ELSE finished_at END, "
                    "error_code=NULL, error_message=NULL WHERE id=?",
                    (state, remote_id, state, self._now_iso(), row["id"]),
                )
                self.db.execute(
                    "UPDATE entity_platform_status SET external_id=COALESCE(NULLIF(external_id,''),?), "
                    "status=CASE WHEN ? IN ('published','completed') THEN 'published' ELSE status END, "
                    "last_status_sync_at=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                    (remote_id, state, self._now_iso(), row["entity_type"], row["entity_id"], platform, account_id),
                )
                return "repaired"

        candidates = self._inventory_candidates(mod, row)
        if candidates is None:
            self.db.execute(
                "UPDATE publish_attempts SET status='unknown', error_code='REMOTE_INVENTORY_UNAVAILABLE', error_message=? WHERE id=?",
                ("remote inventory unavailable; retry recovery later", row["id"]),
            )
            return "unresolved"
        if len(candidates) == 1:
            item = candidates[0]
            rid = str(item.external_id or "").strip()
            if not rid:
                return "unresolved"
            state = str(getattr(item, "status", "published") or "published")
            self.db.execute(
                "UPDATE publish_attempts SET status=?, remote_object_id=?, finished_at=?, "
                "error_code=NULL, error_message=NULL WHERE id=?",
                (state, rid, self._now_iso(), row["id"]),
            )
            self.db.execute(
                "UPDATE entity_platform_status SET external_id=?, external_url=?, status=CASE "
                "WHEN ?='published' THEN 'published' ELSE status END, last_status_sync_at=? "
                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                (rid, getattr(item, "url", "") or None, state, self._now_iso(), row["entity_type"], row["entity_id"], platform, account_id),
            )
            return "repaired"
        if len(candidates) > 1:
            self.db.execute(
                "UPDATE publish_attempts SET status='unknown', error_code='AMBIGUOUS_REMOTE_MATCH', error_message=? WHERE id=?",
                (f"{len(candidates)} remote matches", row["id"]),
            )
            return "ambiguous"
        if self._timed_out(row):
            self._timeout(row)
            return "failed"
        return "unresolved"

    def _inventory_candidates(self, mod: Any, row: dict[str, Any]) -> list[Any] | None:
        try:
            page = mod.list_remote_items(limit=50)
        except NotSupported:
            return []
        except Exception as exc:
            logger.warning("remote inventory unavailable for %s: %s", row.get("platform"), type(exc).__name__)
            return None
        title = self._entity_title(str(row.get("entity_type") or ""), int(row.get("entity_id") or 0))
        title = title.strip().casefold()
        if not title:
            return []
        items = list(getattr(page, "items", []) or [])
        exact = [x for x in items if str(getattr(x, "title", "") or "").strip().casefold() == title]
        return exact

    def _timed_out(self, row: dict[str, Any]) -> bool:
        raw = str(row.get("started_at") or "")
        if not raw:
            return False
        try:
            started = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            now = self.clock.now() if self.clock is not None else datetime.now(UTC)
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            if now.tzinfo is None:
                now = now.replace(tzinfo=UTC)
            timeout_sec = max(60.0, float(os.getenv("ORCH_PUBLISH_RECOVERY_TIMEOUT_SEC", "1800")))
            return now - started >= timedelta(seconds=timeout_sec)
        except Exception:
            logger.debug("publish recovery timeout parse failed", exc_info=True)
            return False

    def _timeout(self, row: dict[str, Any]) -> None:
        now = self._now_iso()
        self.db.execute(
            "UPDATE publish_attempts SET status='failed', error_code='PUBLISH_RECOVERY_TIMEOUT', "
            "error_message='no authoritative remote result within recovery timeout', finished_at=? WHERE id=?",
            (now, row["id"]),
        )
        self.db.execute(
            "UPDATE entity_platform_status SET status='error', last_error='publish_recovery_timeout', last_status_sync_at=? "
            "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? "
            "AND status IN ('publishing','ready','scheduled','updating')",
            (now, row["entity_type"], row["entity_id"], row.get("platform"), row.get("account_id") or ""),
        )
        logger.error("publish recovery timeout: %s", row.get("id"))

    def _entity_title(self, entity_type: str, entity_id: int) -> str:
        table = "shorts" if entity_type == "short" else "long_videos" if entity_type == "long_video" else None
        if table is None:
            return ""
        row = self.db.fetchone(f"SELECT title_text, title FROM {table} WHERE id=?", (entity_id,))
        if not row:
            return ""
        return str(row.get("title_text") or row.get("title") or "")

    def _now_iso(self) -> str:
        if self.clock is not None:
            return self.clock.now().isoformat()
        from datetime import UTC, datetime
        return datetime.now(UTC).isoformat()
