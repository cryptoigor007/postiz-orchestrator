"""Module-based EPS reconciliation (replaces platform two-way recon)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReconStatusFailure:
    code: str
    detail: str


@dataclass
class ReconResult:
    checked: int = 0
    updated: int = 0
    missing: int = 0
    orphans: int = 0
    errors: list[str] = field(default_factory=list)


class ModuleReconciliation:
    """EPS external_id → module.get_status; missing streak; remote orphans → review."""

    def __init__(
        self,
        db: Any,
        cfg: Any,
        clock: Any,
        *,
        module_registry: Any = None,
        missing_threshold: int = 3,
        media_host: Any = None,
    ) -> None:
        self.db = db
        self.cfg = cfg
        self.clock = clock
        self._registry = module_registry
        self.missing_threshold = missing_threshold
        self.media_host = media_host

    def run(self) -> ReconResult:
        res = ReconResult()
        rows = self.db.fetchall(
            """
            SELECT entity_type, entity_id, platform, account_id, external_id, status, last_error, scheduled_for
            FROM entity_platform_status
            WHERE status IN (
                'scheduled', 'scheduled_platform', 'publishing', 'uploaded_inbox',
                'waiting_manual_publish', 'published'
            )
            """
        )
        for r in rows or []:
            res.checked += 1
            ext = (r.get("external_id") or "").strip()
            platform = r.get("platform") or ""
            if not ext:
                # past-due scheduled without external_id → error/retry
                sched = r.get("scheduled_for")
                if sched and r.get("status") in ("scheduled", "publishing"):
                    try:
                        from datetime import datetime, timezone
                        st = datetime.fromisoformat(str(sched).replace("Z", "+00:00"))
                        if st.tzinfo is None:
                            st = st.replace(tzinfo=timezone.utc)
                        if self.clock.now() > st:
                            self.db.execute(
                                "UPDATE entity_platform_status SET status='error', "
                                "last_error='past_due_no_external_id' "
                                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                                (r["entity_type"], r["entity_id"], platform, r.get("account_id") or ""),
                            )
                            res.updated += 1
                    except Exception as exc:
                        msg = f"past_due update failed: {type(exc).__name__}: {exc}"
                        logger.exception("reconciliation past_due update failed for %s/%s/%s", r.get("entity_type"), r.get("entity_id"), platform)
                        res.errors.append(msg)
                continue
            st = self._module_status(platform, ext, str(r.get("account_id") or ""))
            if isinstance(st, ReconStatusFailure):
                detail = str(st.detail or "")[:280]
                last_error = f"status_sync_error:{st.code}:{detail}"[:300]
                self.db.execute(
                    "UPDATE entity_platform_status SET last_error=? "
                    "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                    (last_error, r["entity_type"], r["entity_id"], platform, r.get("account_id") or ""),
                )
                res.errors.append(f"{platform}/{ext}: {st.code}: {detail}")
                continue
            if st is None:
                prev = r.get("last_error") or ""
                streak = 0
                if prev.startswith("missing_on_platform:"):
                    try:
                        streak = int(prev.split(":")[1])
                    except Exception:
                        streak = 1
                streak += 1
                res.missing += 1
                if streak >= self.missing_threshold:
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='error', last_error=? "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        (f"missing_on_platform:{streak}", r["entity_type"], r["entity_id"], platform, r.get("account_id") or ""),
                    )
                    res.updated += 1
                else:
                    self.db.execute(
                        "UPDATE entity_platform_status SET last_error=? "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        (f"missing_on_platform:{streak}", r["entity_type"], r["entity_id"], platform, r.get("account_id") or ""),
                    )
                continue
            state = getattr(st, "state", None) or getattr(st, "status", None) or ""
            if state == "published" and r["status"] != "published":
                self.db.execute(
                    "UPDATE entity_platform_status SET status='published', "
                    "external_url=COALESCE(?, external_url), last_error=NULL "
                    "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                    (getattr(st, "url", None), r["entity_type"], r["entity_id"], platform, r.get("account_id") or ""),
                )
                res.updated += 1
        # remote orphans → review queue (remote_uploads without match)
        try:
            orphans = self.db.fetchall(
                """
                SELECT ru.id, ru.platform, ru.external_id FROM remote_uploads ru
                LEFT JOIN remote_upload_matches m ON m.remote_upload_id = ru.id
                WHERE m.id IS NULL
                LIMIT 50
                """
            )
            res.orphans = len(orphans or [])
        except Exception as exc:
            msg = f"orphan scan failed: {type(exc).__name__}: {exc}"
            logger.exception("reconciliation orphan scan failed")
            res.errors.append(msg)
        return res

    def _module_status(self, platform: str, external_id: str, account_id: str = "") -> Any:
        try:
            from .platforms import default_registry, resolve_engine
            from .platforms.base import ModuleError, ModuleErrorCode, NotSupported
            eng = str(self.cfg.engine_for(platform) or "").strip()
            resolved = resolve_engine(eng)
            if resolved.kind != "module" or not resolved.module_id:
                return None
            reg = self._registry or default_registry()
            if not reg.has(resolved.module_id):
                return None
            from .auth_tokens import token_provider_for
            mod = reg.create(
                resolved.module_id, cfg=self.cfg, dry_run=False, http=None,
                token_provider=token_provider_for(platform), account_id=account_id, media_host=self.media_host,
            )
            return mod.get_status(external_id)
        except ModuleError as exc:
            logger.warning("recon get_status module failure %s %s: %s", platform, external_id, exc.code)
            return ReconStatusFailure(str(exc.code), str(exc))
        except NotSupported as exc:
            logger.info("recon get_status not supported %s %s", platform, external_id)
            return ReconStatusFailure("NOT_SUPPORTED", str(exc))
        except Exception as exc:
            logger.exception("recon get_status failed %s %s", platform, external_id)
            return ReconStatusFailure("FATAL", f"{type(exc).__name__}: {exc}")
