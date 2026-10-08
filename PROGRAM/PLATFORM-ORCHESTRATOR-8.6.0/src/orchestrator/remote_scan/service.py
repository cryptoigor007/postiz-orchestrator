"""RemoteScanService: module.list_remote_items → remote_uploads → match/claim.

MVP match: project isolation + one-candidate auto-claim only.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..manual_uploads import match_score, normalize_title

logger = logging.getLogger(__name__)

AUTO_CLAIM_MIN = 0.8
REVIEW_MIN = 0.5


@dataclass
class ScanResult:
    platform: str
    items_seen: int = 0
    pages: int = 0
    auto_claimed: int = 0
    pending_review: int = 0
    orphans: int = 0
    partial: bool = False
    error: str = ""


def match_candidates(
    remote: dict[str, Any],
    entities: list[dict[str, Any]],
    *,
    auto_min: float = AUTO_CLAIM_MIN,
    review_min: float = REVIEW_MIN,
) -> tuple[str, dict[str, Any] | None, float, dict]:
    """Return (decision, entity|None, score, parts).

    decision: auto_claimed | pending_review | ignored
    Auto-claim ONLY if exactly one candidate above auto_min.
    Two close scores → pending_review.
    """
    scored: list[tuple[float, dict, dict]] = []
    for e in entities:
        s, parts = match_score(remote, e)
        if s >= review_min:
            scored.append((s, e, parts))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return "ignored", None, 0.0, {}
    top_score, top_ent, top_parts = scored[0]
    above_auto = [x for x in scored if x[0] >= auto_min]
    if len(above_auto) == 1:
        return "auto_claimed", above_auto[0][1], above_auto[0][0], above_auto[0][2]
    if len(above_auto) >= 2:
        return "pending_review", top_ent, top_score, top_parts
    if top_score >= review_min:
        return "pending_review", top_ent, top_score, top_parts
    return "ignored", None, top_score, top_parts


class RemoteScanService:
    def __init__(
        self,
        db: Any,
        cfg: Any,
        *,
        module_registry: Any = None,
        auto_claim_min: float = AUTO_CLAIM_MIN,
        review_min: float = REVIEW_MIN,
        lookback_days: int = 90,
        media_host: Any = None,
    ) -> None:
        self.db = db
        self.cfg = cfg
        self._registry = module_registry
        self.auto_claim_min = auto_claim_min
        self.review_min = review_min
        self.lookback_days = lookback_days
        self.media_host = media_host

    def scan_platform(self, platform: str, *, account_id: str = "") -> ScanResult:
        result = ScanResult(platform=platform)
        try:
            from ..platforms import default_registry, resolve_engine
        except Exception as e:
            result.error = f"registry: {e}"
            return result
        eng = str(self.cfg.engine_for(platform) or "").strip()
        try:
            resolved = resolve_engine(eng)
        except ValueError:
            result.error = f"engine not module: {eng!r}"
            return result
        if resolved.kind != "module" or not resolved.module_id:
            result.error = "not a module engine"
            return result
        reg = self._registry or default_registry()
        if not reg.has(resolved.module_id):
            result.error = f"module {resolved.module_id!r} not registered"
            return result
        try:
            from ..auth_tokens import token_provider_for
            mod = reg.create(
                resolved.module_id, cfg=self.cfg, dry_run=False, http=None,
                token_provider=token_provider_for(platform), media_host=self.media_host,
                account_id=str(account_id or ""),
            )
        except Exception as e:
            result.error = f"create: {e}"
            return result

        since = datetime.now(UTC) - timedelta(days=self.lookback_days)
        cursor = None
        started = datetime.now(UTC).isoformat()
        scan_id = None
        try:
            self.db.execute(
                """
                INSERT INTO remote_scans
                    (platform, account_id, started_at, lookback_days, status, scan_reason)
                VALUES (?, ?, ?, ?, 'running', 'scheduled')
                """,
                (platform, account_id or None, started, self.lookback_days),
            )
            row = self.db.fetchone(
                "SELECT id FROM remote_scans WHERE platform=? AND started_at=? ORDER BY id DESC LIMIT 1",
                (platform, started),
            )
            scan_id = row["id"] if row else None
        except Exception:
            logger.debug("remote_scans insert failed", exc_info=True)

        try:
            while True:
                try:
                    page = mod.list_remote_items(
                        kinds={"published", "scheduled", "private", "processing"},
                        since=since,
                        limit=50,
                        cursor=cursor,
                    )
                except Exception as _lr:
                    from ..platforms.base import NotSupported, RemotePage, RemoteItem
                    if not isinstance(_lr, NotSupported) and type(_lr).__name__ != "NotSupported":
                        # legacy list_remote(list) adapter
                        if hasattr(mod, "list_remote"):
                            raw = mod.list_remote(limit=50)
                            items = []
                            for it in raw or []:
                                if isinstance(it, dict):
                                    items.append(RemoteItem(
                                        platform=platform,
                                        external_id=str(it.get("id") or it.get("external_id") or ""),
                                        title=str(it.get("title") or ""),
                                        status=str(it.get("status") or "published"),
                                        url=str(it.get("url") or it.get("link") or ""),
                                    ))
                            page = RemotePage(items=items, partial=True, notes=["adapted from list_remote"])
                            cursor = None
                        else:
                            raise
                    else:
                        raise
                result.pages += 1
                if getattr(page, "partial", False):
                    result.partial = True
                for it in page.items or []:
                    result.items_seen += 1
                    self._upsert_and_match(platform, it, result)
                cursor = getattr(page, "next_cursor", None)
                if not cursor or result.pages >= 20:
                    break
        except Exception as e:
            from ..platforms.base import NotSupported
            if isinstance(e, NotSupported):
                result.error = "list_remote_items unsupported"
            else:
                result.error = f"{type(e).__name__}: {e}"
                logger.warning("remote scan %s failed: %s", platform, e, exc_info=True)

        if scan_id is not None:
            try:
                self.db.execute(
                    """
                    UPDATE remote_scans SET finished_at=?, pages=?, items_seen=?,
                        partial=?, status=?, error=? WHERE id=?
                    """,
                    (
                        datetime.now(UTC).isoformat(),
                        result.pages,
                        result.items_seen,
                        1 if result.partial else 0,
                        "error" if result.error else "done",
                        result.error or None,
                        scan_id,
                    ),
                )
            except Exception:
                logger.debug("remote scan result persistence failed", exc_info=True)
        return result

    def _upsert_and_match(self, platform: str, it: Any, result: ScanResult) -> None:
        now = datetime.now(UTC).isoformat()
        ext = getattr(it, "external_id", None) or ""
        if not ext:
            return
        remote = {
            "title": getattr(it, "title", "") or "",
            "published_at": getattr(it, "published_at", None),
            "scheduled_for": getattr(it, "scheduled_for", None),
            "duration_sec": getattr(it, "duration_sec", None),
            "platform": platform,
            "external_id": ext,
        }
        try:
            self.db.execute(
                """
                INSERT INTO remote_uploads
                    (platform, external_id, url, title, description, published_at,
                     scheduled_for, privacy, status, duration_sec, thumb_url, media_type,
                     first_seen_at, last_seen_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, external_id) DO UPDATE SET
                    url=COALESCE(excluded.url, remote_uploads.url),
                    title=COALESCE(excluded.title, remote_uploads.title),
                    last_seen_at=excluded.last_seen_at,
                    status=COALESCE(excluded.status, remote_uploads.status),
                    privacy=COALESCE(excluded.privacy, remote_uploads.privacy)
                """,
                (
                    platform, ext,
                    getattr(it, "url", "") or "",
                    getattr(it, "title", "") or "",
                    getattr(it, "description", "") or "",
                    getattr(it, "published_at", None),
                    getattr(it, "scheduled_for", None),
                    getattr(it, "privacy", "") or "",
                    getattr(it, "status", "") or "",
                    getattr(it, "duration_sec", None),
                    getattr(it, "thumb_url", "") or "",
                    getattr(it, "media_type", "video") or "video",
                    now, now,
                    json.dumps(getattr(it, "raw", None) or {}, ensure_ascii=False),
                ),
            )
        except Exception:
            logger.debug("upsert remote_uploads failed", exc_info=True)
            return

        # Candidates: local entities without external_id on this platform
        entities = self._candidate_entities(platform)
        decision, ent, score, parts = match_candidates(
            remote, entities,
            auto_min=self.auto_claim_min, review_min=self.review_min,
        )
        rup = self.db.fetchone(
            "SELECT id FROM remote_uploads WHERE platform=? AND external_id=?",
            (platform, ext),
        )
        if not rup:
            return
        rid = rup["id"]
        if decision == "ignored" or ent is None:
            result.orphans += 1
            return
        et = ent.get("entity_type") or "short"
        eid = int(ent.get("entity_id") or ent.get("id") or 0)
        try:
            self.db.execute(
                """
                INSERT INTO remote_upload_matches
                    (remote_upload_id, entity_type, entity_id, score, score_parts_json,
                     decision, decided_at, decided_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'system')
                ON CONFLICT(remote_upload_id, entity_type, entity_id) DO UPDATE SET
                    score=excluded.score, decision=excluded.decision, decided_at=excluded.decided_at
                """,
                (
                    rid, et, eid, score,
                    json.dumps(parts, ensure_ascii=False),
                    decision, now,
                ),
            )
        except Exception:
            logger.debug("match insert failed", exc_info=True)
        if decision == "auto_claimed":
            self._claim(et, eid, platform, ext, getattr(it, "url", "") or "")
            result.auto_claimed += 1
        elif decision == "pending_review":
            result.pending_review += 1

    def _candidate_entities(self, platform: str) -> list[dict[str, Any]]:
        """Entities missing external_id on platform (and no platform id)."""
        out: list[dict[str, Any]] = []
        try:
            # shorts without binding on this platform
            rows = self.db.fetchall(
                """
                SELECT s.id AS entity_id, 'short' AS entity_type,
                       s.title_text AS title, s.created_at AS published_at
                FROM shorts s
                WHERE NOT EXISTS (
                    SELECT 1 FROM entity_platform_status eps
                    WHERE eps.entity_type='short' AND eps.entity_id=s.id
                      AND eps.platform=?
                      AND (
                        (eps.external_id IS NOT NULL AND eps.external_id != '')
                      )
                )
                LIMIT 500
                """,
                (platform,),
            )
            out.extend(rows or [])
        except Exception:
            logger.debug("candidate query failed", exc_info=True)
        return out

    def _claim(
        self, entity_type: str, entity_id: int, platform: str,
        external_id: str, url: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        try:
            self.db.execute(
                """
                INSERT INTO entity_platform_status
                    (entity_type, entity_id, platform, status, external_id, external_url,
                     source, published_at)
                VALUES (?, ?, ?, 'published', ?, ?, 'remote_scan', ?)
                ON CONFLICT(entity_type, entity_id, platform, account_id) DO UPDATE SET
                    external_id=excluded.external_id,
                    external_url=COALESCE(excluded.external_url, entity_platform_status.external_url),
                    source='remote_scan',
                    status=CASE
                        WHEN entity_platform_status.status IN ('published','scheduled')
                        THEN entity_platform_status.status ELSE 'published' END
                """,
                (entity_type, entity_id, platform, external_id, url or None, now),
            )
            self.db.log(entity_type, entity_id, platform, "remote_claim", external_id)
        except Exception:
            logger.warning("claim failed %s/%s %s", entity_type, entity_id, platform, exc_info=True)
