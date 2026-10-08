from __future__ import annotations

import logging
from datetime import UTC, datetime
from dataclasses import dataclass
from typing import Any

from .clock import Clock
from .config import AppConfig
from .db import Database

# removed in C13/R8 — local helpers
def is_thumbnail_only_error(x: Any) -> bool:
    return False


def short_reason(msg: Any, limit: int = 300) -> str:
    return (str(msg) if msg else "")[:limit]


logger = logging.getLogger(__name__)

# Причина обложки пишется предупреждением: публикация состоялась, но без миниатюры.
THUMBNAIL_WARN_PREFIX = "Опубликовано без обложки"
ERROR_REASON_LIMIT = 300
# Уведомление об ошибке не содержит id поста — сопоставляем по платформе и времени.
ERROR_MATCH_WINDOW_SEC = 3600
DEFAULT_MISSING_THRESHOLD = 3

@dataclass(frozen=True)
class _StatusFetchFailure:
    code: str
    detail: str


class StatusSync:
    """Module-only status pull for EPS rows with external_id.

    No platform client or legacy EPS field is required. Uses module.get_status only.
    """

    def __init__(
        self,
        db: Database,
        clock: Clock,
        cfg: AppConfig,
        registry: Any = None,
        *,
        modules: Any = None,
        module_registry: Any = None,
    ):
        self.db = db
        self.clock = clock
        self.cfg = cfg
        # Accept registry | modules | module_registry (no platform kwarg).
        self._module_registry = registry or modules or module_registry

    def sync(self, fresh_only: bool = False) -> int:
        """Pull status via module.get_status for rows with external_id.

        If fresh_only — only posts scheduled within confirm_published_interval
        window around now (uses scheduled_for, falls back to legacy column if present).
        """
        sql = """
            SELECT entity_type, entity_id, platform, account_id, status,
                   release_url, last_error,
                   external_id, external_url, scheduled_for, source
            FROM entity_platform_status
            WHERE (
                external_id IS NOT NULL AND external_id != ''
              )
              AND (
                status IN ('scheduled', 'updating', 'error', 'publishing',
                           'scheduled_platform', 'uploaded_inbox', 'waiting_manual_publish')
                OR (status='published' AND (release_url IS NULL OR release_url=''
                    OR external_url IS NULL OR external_url=''))
              )
        """
        rows = self.db.fetchall(sql)
        if fresh_only:
            window = self.cfg.confirm_published_interval_sec
            now = self.clock.now()
            filtered = []
            for r in rows:
                sched = r.get("scheduled_for")
                if not sched:
                    filtered.append(r)
                    continue
                try:
                    st = datetime.fromisoformat(str(sched).replace("Z", "+00:00"))
                    if st.tzinfo is None:
                        st = st.replace(tzinfo=UTC)
                    if abs((st - now).total_seconds()) <= window * 3:
                        filtered.append(r)
                except Exception:
                    filtered.append(r)
            rows = filtered
        updated = 0
        for row in rows:
            try:
                post = self._fetch_status(row)
            except Exception as exc:
                failure = _StatusFetchFailure("FATAL", f"{type(exc).__name__}: {exc}")
                logger.exception(
                    "get_status failed for %s/%s/%s (skip)",
                    row.get("platform"), row.get("entity_type"), row.get("entity_id"),
                )
                post = failure
            if isinstance(post, _StatusFetchFailure):
                detail = short_reason(post.detail, ERROR_REASON_LIMIT)
                last_error = short_reason(f"status_sync_error:{post.code}:{detail}", ERROR_REASON_LIMIT)
                self.db.execute(
                    "UPDATE entity_platform_status SET last_error=? "
                    "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                    (last_error, row["entity_type"], row["entity_id"], row["platform"], row.get("account_id") or ""),
                )
                logger.warning(
                    "status sync non-missing failure %s/%s/%s code=%s detail=%s",
                    row.get("entity_type"), row.get("entity_id"), row.get("platform"), post.code, detail,
                )
                updated += 1
                continue
            if not post:
                # N consecutive misses → error (soft: first misses only warn)
                prev = row.get("last_error") or ""
                streak = 0
                if prev.startswith("missing_on_platform:"):
                    try:
                        streak = int(prev.split(":")[1])
                    except Exception:
                        streak = 1
                streak += 1
                threshold = int(
                    getattr(self.cfg, "missing_error_after", None)
                    or getattr(self.cfg, "missing_error_after", None)
                    or DEFAULT_MISSING_THRESHOLD
                )
                if streak >= threshold:
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='error', "
                        "last_error=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        (f"missing_on_platform:{streak}",
                         row["entity_type"], row["entity_id"], row["platform"], row.get("account_id") or ""),
                    )
                else:
                    self.db.execute(
                        "UPDATE entity_platform_status SET last_error=? "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        (f"missing_on_platform:{streak}",
                         row["entity_type"], row["entity_id"], row["platform"], row.get("account_id") or ""),
                    )
                    logger.warning(
                        "get_status miss %s/%s/%s streak=%s/%s",
                        row["entity_type"], row["entity_id"], row["platform"],
                        streak, threshold,
                    )
                updated += 1
                continue
            st = self._normalize_status(getattr(post, "status", None))
            if st == "error":
                prev_err = str(row.get("last_error") or "")
                if row["status"] == "published" and prev_err.startswith(THUMBNAIL_WARN_PREFIX):
                    continue
                reason = short_reason(getattr(post, "error", None), ERROR_REASON_LIMIT)
                if is_thumbnail_only_error(reason):
                    now = self.clock.now().isoformat()
                    warn = short_reason(
                        f"{THUMBNAIL_WARN_PREFIX}: {reason}", ERROR_REASON_LIMIT
                    )
                    self.db.execute(
                        """
                        UPDATE entity_platform_status
                        SET status='published', published_at=?,
                            release_url=COALESCE(?, release_url),
                            last_error=?
                        WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?
                        """,
                        (now, post.release_url, warn,
                         row["entity_type"], row["entity_id"], row["platform"], row.get("account_id") or ""),
                    )
                    self.db.log(
                        row["entity_type"], row["entity_id"], row["platform"],
                        "published_without_cover", short_reason(reason),
                    )
                    logger.warning(
                        "platform %s/%s %s — published without cover: %s",
                        row["entity_type"], row["entity_id"], row["platform"], reason,
                    )
                    updated += 1
                    continue
                msg = (
                    short_reason(f"Ошибка площадки: {reason}", ERROR_REASON_LIMIT)
                    if reason
                    else "platform_error"
                )
                if row["status"] != "error" or msg != prev_err:
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='error', last_error=? "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        (msg, row["entity_type"], row["entity_id"], row["platform"], row.get("account_id") or ""),
                    )
                    updated += 1
                if post.release_url and not row.get("release_url"):
                    self.db.execute(
                        "UPDATE entity_platform_status SET release_url=? "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? "
                        "AND (release_url IS NULL OR release_url='')",
                        (post.release_url, row["entity_type"], row["entity_id"],
                         row["platform"], row.get("account_id") or ""),
                    )
                    updated += 1
                continue
            if st == "published" and row["status"] != "published":
                now = self.clock.now().isoformat()
                self.db.execute(
                    """
                    UPDATE entity_platform_status
                    SET status='published', published_at=?,
                        release_url=COALESCE(?, release_url),
                        external_url=COALESCE(?, external_url),
                        last_error=NULL
                    WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?
                    """,
                    (
                        now,
                        post.release_url,
                        post.release_url,
                        row["entity_type"],
                        row["entity_id"],
                        row["platform"],
                        row.get("account_id") or "",
                    ),
                )
                updated += 1
            elif st == "published" and post.release_url and not row.get("release_url"):
                self.db.execute(
                    "UPDATE entity_platform_status SET release_url=?, "
                    "external_url=COALESCE(external_url, ?) "
                    "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? "
                    "AND (release_url IS NULL OR release_url='')",
                    (
                        post.release_url,
                        post.release_url,
                        row["entity_type"],
                        row["entity_id"],
                        row["platform"],
                        row.get("account_id") or "",
                    ),
                )
                updated += 1
            else:
                # Recover false missing_on_platform / reconciliation_missing
                prev_err = row.get("last_error") or ""
                if prev_err.startswith("missing_on_platform:") or (
                    row["status"] == "error" and prev_err == "reconciliation_missing"
                ):
                    new_status = row["status"]
                    if new_status == "error":
                        new_status = st if st in ("scheduled", "updating") else "scheduled"
                    self.db.execute(
                        "UPDATE entity_platform_status SET status=?, last_error=NULL "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        (new_status, row["entity_type"], row["entity_id"], row["platform"], row.get("account_id") or ""),
                    )
                    updated += 1
                    logger.info(
                        "Recovered %s/%s/%s from %s -> %s",
                        row["entity_type"], row["entity_id"], row["platform"],
                        prev_err, new_status,
                    )
        return updated

    def _fetch_status(self, row: dict) -> Any:
        """Module get_status only — no platform fallback."""
        ext = (row.get("external_id") or "").strip()
        if not ext:
            return None
        return self._module_get_status(str(row.get("platform") or ""), ext, str(row.get("account_id") or ""))

    def _module_get_status(self, platform: str, external_id: str, account_id: str = "") -> Any:
        try:
            from .platforms import default_registry, resolve_engine
            from .platforms.base import ModuleError, NotSupported
        except Exception as exc:
            return _StatusFetchFailure("FATAL", f"import failed: {type(exc).__name__}: {exc}")
        eng = str(self.cfg.engine_for(platform) or "").strip()
        try:
            resolved = resolve_engine(eng)
        except ValueError as exc:
            return _StatusFetchFailure("FATAL", f"engine resolution: {exc}")
        if resolved.kind != "module" or not resolved.module_id:
            return _StatusFetchFailure("NOT_SUPPORTED", f"engine is not module for {platform}")
        reg = self._module_registry or default_registry()
        if not reg.has(resolved.module_id):
            return _StatusFetchFailure("FATAL", f"module {resolved.module_id} is not registered")
        try:
            from .auth_tokens import token_provider_for
            mod = reg.create(
                resolved.module_id,
                cfg=self.cfg,
                dry_run=False,
                http=None,
                token_provider=token_provider_for(platform),
                account_id=account_id,
                media_host=getattr(self, "media_host", None),
            )
            st = mod.get_status(external_id)
        except NotSupported as exc:
            return _StatusFetchFailure("NOT_SUPPORTED", str(exc))
        except ModuleError as exc:
            return _StatusFetchFailure(str(exc.code), exc.message)
        except Exception as exc:
            logger.exception("module get_status failed %s %s", platform, external_id)
            return _StatusFetchFailure("FATAL", f"{type(exc).__name__}: {exc}")

        class _Adapt:
            pass

        a = _Adapt()
        a.status = getattr(st, "state", None) or getattr(st, "status", None) or "unknown"
        a.release_url = getattr(st, "url", None) or ""
        a.id = external_id
        a.error = getattr(st, "error", None) or ""
        return a

    @staticmethod
    def _normalize_status(raw: str | None) -> str:
        """Map platform state strings to local statuses."""
        if not raw:
            return ""
        s = str(raw).strip().lower()
        if s in ("published", "released", "completed", "done", "live"):
            return "published"
        if s in ("error", "failed", "rejected"):
            return "error"
        if s in ("scheduled", "pending", "queue", "queued"):
            return "scheduled"
        if s in ("updating", "draft"):
            return "updating"
        if s in ("uploaded_inbox", "inbox"):
            return "uploaded_inbox"
        if s in ("waiting_manual_publish", "manual"):
            return "waiting_manual_publish"
        return s


# Reconciliation removed in R8 (was platform two-way sync); module recon in F19
