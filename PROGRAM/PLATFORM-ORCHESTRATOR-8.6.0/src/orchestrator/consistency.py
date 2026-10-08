"""Periodic local-vs-remote consistency sweep with conservative repair."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable


class ConsistencySweeper:
    def __init__(self, db: Any, registry: Any, cfg: Any, *, module_factory: Callable[..., Any] | None = None):
        self.db = db
        self.registry = registry
        self.cfg = cfg
        self.module_factory = module_factory or registry.create

    def sweep(self, platform: str, account_id: str = "", *, limit: int = 100) -> dict[str, int | str]:
        platform = str(platform or "").strip().lower()
        account_id = str(account_id or "")
        start = datetime.now(UTC).isoformat()
        run_id = self.db.execute(
            "INSERT INTO consistency_runs(platform, account_id, started_at) VALUES (?, ?, ?)",
            (platform, account_id, start),
        )
        scanned = repaired = conflicts = 0
        try:
            rows = self.db.fetchall(
                "SELECT entity_type, entity_id, account_id, external_id, external_url, status "
                "FROM entity_platform_status "
                "WHERE platform=? AND account_id=? AND external_id IS NOT NULL AND external_id!='' "
                "ORDER BY entity_id LIMIT ?",
                (platform, account_id, max(1, int(limit))),
            )
            scanned = len(rows)
            mod = None
            authoritative = False
            try:
                mod = self.module_factory(platform, account_id=account_id)
                authoritative = str(
                    getattr(getattr(mod, "manifest", None), "status_authority", "unknown") or "unknown"
                ).lower() == "authoritative"
            except Exception:
                mod = None

            if mod is not None and authoritative and hasattr(mod, "get_status"):
                for row in rows:
                    ext = str(row.get("external_id") or "").strip()
                    if not ext:
                        continue
                    try:
                        remote = mod.get_status(ext)
                    except Exception:
                        continue
                    remote_state = str(getattr(remote, "state", "unknown") or "unknown").lower()
                    if remote_state == "unknown":
                        continue
                    remote_url = str(getattr(remote, "url", "") or "").strip()
                    local_state = str(row.get("status") or "").lower()
                    if remote_state != local_state or (remote_url and remote_url != str(row.get("external_url") or "")):
                        conflicts += 1
                        repaired += self.db.execute(
                            "UPDATE entity_platform_status SET status=?, external_url=COALESCE(NULLIF(?, ''), external_url), "
                            "release_url=COALESCE(NULLIF(?, ''), release_url), last_status_sync_at=? "
                            "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                            (
                                remote_state,
                                remote_url,
                                remote_url,
                                datetime.now(UTC).isoformat(),
                                row["entity_type"],
                                row["entity_id"],
                                platform,
                                account_id,
                            ),
                        )

            self.db.execute(
                "UPDATE consistency_runs SET finished_at=?, scanned=?, repaired=?, conflicts=?, status='done' WHERE id=?",
                (datetime.now(UTC).isoformat(), scanned, repaired, conflicts, run_id),
            )
            return {"run_id": run_id, "scanned": scanned, "repaired": repaired, "conflicts": conflicts, "status": "done"}
        except Exception as exc:
            self.db.execute(
                "UPDATE consistency_runs SET finished_at=?, scanned=?, repaired=?, conflicts=?, status='error', error=? WHERE id=?",
                (datetime.now(UTC).isoformat(), scanned, repaired, conflicts, str(exc)[:1000], run_id),
            )
            raise
