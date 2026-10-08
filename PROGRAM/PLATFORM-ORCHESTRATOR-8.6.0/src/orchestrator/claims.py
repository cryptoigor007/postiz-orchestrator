"""YouTube claims job: check K hours before slot; A3 delete+next; telegram buttons."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ClaimsJobResult:
    checked: int = 0
    claimed: int = 0
    clean: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def run_claims_check(
    db: Any,
    *,
    clock: Any,
    youtube_module: Any | None,
    hours_before: float = 6.0,
    notifier: Any | None = None,
    account_id: str = "",
) -> ClaimsJobResult:
    """Check claims for scheduled YT rows within window; update claims_state."""
    res = ClaimsJobResult()
    if youtube_module is None:
        res.errors.append("youtube_module missing")
        return res
    now = clock.now()
    horizon = (now + timedelta(hours=hours_before)).isoformat()
    rows = db.fetchall(
        """
        SELECT entity_type, entity_id, platform, account_id, external_id, scheduled_for, claims_state
        FROM entity_platform_status
        WHERE platform='youtube'
          AND status IN ('scheduled', 'scheduled_platform')
          AND external_id IS NOT NULL AND external_id != ''
          AND scheduled_for IS NOT NULL AND scheduled_for <= ?
          AND (claims_state IS NULL OR claims_state IN ('', 'pending'))
          AND (? = '' OR account_id = ?)
        """,
        (horizon, str(account_id or ''), str(account_id or '')),
    )
    for r in rows or []:
        res.checked += 1
        eid = r["external_id"]
        try:
            cr = youtube_module.check_claims(eid)
        except Exception as e:
            res.errors.append(f"{eid}: {e}")
            continue
        supported = getattr(cr, "supported", False)
        if not supported:
            res.skipped += 1
            db.execute(
                "UPDATE entity_platform_status SET claims_state='unsupported', claims_checked_at=? "
                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                (now.isoformat(), r["entity_type"], r["entity_id"], r["platform"], r["account_id"]),
            )
            continue
        has_claim = bool(getattr(cr, "has_claim", False) or getattr(cr, "claimed", False))
        if has_claim:
            res.claimed += 1
            db.execute(
                "UPDATE entity_platform_status SET claims_state='claimed', claims_checked_at=? "
                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                (now.isoformat(), r["entity_type"], r["entity_id"], r["platform"], r["account_id"]),
            )
            if notifier and hasattr(notifier, "ask_claims"):
                try:
                    notifier.ask_claims(r["entity_type"], r["entity_id"], eid, str(r.get("account_id") or ""))
                except Exception:
                    logger.debug("claims notify failed", exc_info=True)
        else:
            res.clean += 1
            db.execute(
                "UPDATE entity_platform_status SET claims_state='clean', claims_checked_at=? "
                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                (now.isoformat(), r["entity_type"], r["entity_id"], r["platform"], r["account_id"]),
            )
    return res


def a3_delete_and_next(
    db: Any,
    *,
    publisher: Any,
    entity_type: str,
    entity_id: int,
    platform: str,
    youtube_module: Any | None,
    account_id: str = "",
) -> bool:
    """A3: delete platform copy, mark claimed_skipped, queue next same type (publish_log)."""
    row = db.fetchone(
        "SELECT external_id FROM entity_platform_status "
        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
        (entity_type, entity_id, platform, str(account_id or "")),
    )
    if not row:
        return False
    eid = row.get("external_id")
    if eid and youtube_module is not None:
        try:
            youtube_module.delete(eid)
        except Exception:
            logger.warning("A3 delete failed %s", eid, exc_info=True)
    db.execute(
        "UPDATE entity_platform_status SET status='claimed_skipped', claims_state='resolved_a3', "
        "external_id=NULL "
        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
        (entity_type, entity_id, platform, str(account_id or "")),
    )
    try:
        db.log(entity_type, entity_id, platform, "claims_a3_delete", str(eid or ""))
    except Exception:
        logger.debug("claims A3 audit log failed", exc_info=True)
    return True


def resolve_claim_a3(
    db: Any,
    entity_type: str,
    entity_id: int,
    platform: str = "youtube",
    account_id: str = "",
) -> None:
    """A3: mark claimed_skipped and clear external ids so next item can take the slot."""
    row = db.fetchone(
        "SELECT external_id FROM entity_platform_status "
        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
        (entity_type, entity_id, platform, str(account_id or "")),
    )
    eid = (row.get("external_id")) if row else None
    db.execute(
        "UPDATE entity_platform_status SET status='claimed_skipped', claims_state='resolved_a3', "
        "external_id=NULL, last_error='claims_a3' "
        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
        (entity_type, entity_id, platform, str(account_id or "")),
    )
    db.log(entity_type, entity_id, platform, "claims_a3_delete", str(eid or ""))
