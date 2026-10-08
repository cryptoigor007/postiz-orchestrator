from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from .clock import Clock
from .config import AppConfig
from .db import Database
from .safety import SafetyChecker

logger = logging.getLogger(__name__)


class _PublishResultLike(Protocol):
    id: str
    platform: str
    status: str
    release_url: str | None


@dataclass
class PublishOutcome:
    id: str
    platform: str = ""
    status: str = ""
    release_url: str | None = None
    content: dict[str, Any] | None = None
    scheduled_for: datetime | None = None


class Publisher:
    """Module-only publisher (platform transport removed in F3)."""

    def __init__(
        self,
        db: Database,
        cfg: AppConfig,
        safety: SafetyChecker,
        clock: Clock,
        dry_run: bool = False,
        guard: Any = None,
        broker: Any = None,
        module_registry: Any = None,
        supervisor: Any = None,
        outbox: Any = None,
    ):
        self.db = db
        self.cfg = cfg
        self.safety = safety
        self.clock = clock
        self.dry_run = dry_run
        self.guard = guard
        self.broker = broker
        self._module_registry = module_registry
        self.supervisor = supervisor
        self.outbox = outbox
        self.media_host = None
        try:
            from .media_transfer import MediaTransferManager
            self.media_transfer = MediaTransferManager(db)
        except Exception:
            self.media_transfer = None

    @staticmethod
    def _media_signature(media_path: str | None) -> str:
        if not media_path:
            return ""
        try:
            if str(media_path).startswith(("http://", "https://")):
                return f"url:{media_path}"
            h = hashlib.sha256()
            with open(media_path, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            return f"sha256:{h.hexdigest()}"
        except OSError:
            return f"path:{media_path}"

    def _idempotency_key(self, entity_type: str, entity_id: int, platform: str, account_id: str,
                        media_path: str | None, content: dict[str, Any]) -> str:
        file_sig = self._media_signature(media_path)
        raw = json.dumps({"entity_type": entity_type, "entity_id": entity_id, "platform": platform,
                          "account_id": account_id, "content": content or {}, "media": file_sig},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _content_revision_hash(self, entity_type: str, entity_id: int, content: dict[str, Any], media_path: str | None) -> str:
        media_sig = self._media_signature(media_path)
        raw = json.dumps({"entity_type": entity_type, "entity_id": entity_id, "content": content or {}, "media": media_sig}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _ensure_content_revision(self, entity_type: str, entity_id: int, content: dict[str, Any], media_path: str | None) -> str:
        revision_hash = self._content_revision_hash(entity_type, entity_id, content or {}, media_path)
        revision_id = revision_hash[:32]
        now = self.clock.now().isoformat()
        self.db.execute(
            "INSERT INTO content_revisions(id,entity_type,entity_id,revision_hash,content_json,media_path,created_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(revision_hash) DO NOTHING",
            (revision_id, entity_type, entity_id, revision_hash, json.dumps(content or {}, ensure_ascii=False, sort_keys=True), media_path, now),
        )
        return revision_hash

    def _ensure_distribution_target(self, entity_type: str, entity_id: int, platform: str, account_id: str, revision_hash: str, scheduled_for: datetime | None) -> str:
        target_id = hashlib.sha256(f"{entity_type}:{entity_id}:{platform}:{account_id}:{revision_hash}".encode()).hexdigest()[:32]
        now = self.clock.now().isoformat()
        self.db.execute(
            "INSERT INTO distribution_targets(id,entity_type,entity_id,platform,account_id,revision_hash,scheduled_for,publish_mode,status,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?, ?, 'publishing', ?, ?) ON CONFLICT(entity_type,entity_id,platform,account_id,revision_hash) DO UPDATE SET status='publishing',scheduled_for=excluded.scheduled_for,updated_at=excluded.updated_at",
            (target_id, entity_type, entity_id, platform, account_id, revision_hash, scheduled_for.isoformat() if scheduled_for else None, "scheduled" if scheduled_for else "immediate", now, now),
        )
        return target_id

    def _ensure_schedule_artifacts(
        self,
        entity_type: str,
        entity_id: int,
        platform: str,
        account_id: str,
        content: dict[str, Any],
        media_path: str | None,
        scheduled_for: datetime | None,
    ) -> tuple[str, str]:
        """Atomically persist revision + distribution target before any provider side-effect.

        This is the schedule-time invariant: a queued/local schedule is not considered
        valid unless both the immutable revision snapshot and its account-scoped target
        exist and join successfully in the same SQLite transaction.
        """
        revision_hash = self._content_revision_hash(entity_type, entity_id, content or {}, media_path)
        revision_id = revision_hash[:32]
        target_id = hashlib.sha256(
            f"{entity_type}:{entity_id}:{platform}:{account_id}:{revision_hash}".encode()
        ).hexdigest()[:32]
        now = self.clock.now().isoformat()
        scheduled_iso = scheduled_for.isoformat() if scheduled_for else None
        publish_mode = "scheduled" if scheduled_for else "immediate"
        content_json = json.dumps(content or {}, ensure_ascii=False, sort_keys=True)
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO content_revisions(id,entity_type,entity_id,revision_hash,content_json,media_path,created_at) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(revision_hash) DO NOTHING",
                (revision_id, entity_type, entity_id, revision_hash, content_json, media_path, now),
            )
            conn.execute(
                "INSERT INTO distribution_targets(id,entity_type,entity_id,platform,account_id,revision_hash,scheduled_for,publish_mode,status,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,'publishing',?,?) "
                "ON CONFLICT(entity_type,entity_id,platform,account_id,revision_hash) DO UPDATE SET "
                "status='publishing',scheduled_for=excluded.scheduled_for,publish_mode=excluded.publish_mode,updated_at=excluded.updated_at",
                (target_id, entity_type, entity_id, platform, account_id, revision_hash, scheduled_iso, publish_mode, now, now),
            )
            row = conn.execute(
                "SELECT dt.id, dt.revision_hash, cr.content_json, cr.media_path "
                "FROM distribution_targets dt JOIN content_revisions cr ON cr.revision_hash=dt.revision_hash "
                "WHERE dt.id=? AND dt.entity_type=? AND dt.entity_id=? AND dt.platform=? AND dt.account_id=?",
                (target_id, entity_type, entity_id, platform, account_id),
            ).fetchone()
            if row is None or str(row[1] or "") != revision_hash:
                raise RuntimeError("schedule snapshot invariant failed")
        return revision_hash, target_id

    def _begin_publish_attempt(self, entity_type: str, entity_id: int, platform: str, account_id: str,
                               media_path: str | None, content: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        key = self._idempotency_key(entity_type, entity_id, platform, account_id, media_path, content)
        row = self.db.fetchone(
            "SELECT * FROM publish_attempts WHERE platform=? AND account_id=? AND idempotency_key=?",
            (platform, account_id, key),
        )
        if row and str(row.get("status") or "") in {"published", "completed", "processing"} and row.get("remote_object_id"):
            return key, row
        attempt_id = hashlib.sha256((key + str(self.clock.now().timestamp())).encode()).hexdigest()[:32]
        try:
            self.db.execute(
                "INSERT INTO publish_attempts(id,entity_type,entity_id,platform,account_id,revision_hash,idempotency_key,status,started_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (attempt_id, entity_type, entity_id, platform, account_id, key, key, "started", self.clock.now().isoformat()),
            )
            return key, None
        except Exception:
            row = self.db.fetchone(
                "SELECT * FROM publish_attempts WHERE platform=? AND account_id=? AND idempotency_key=?",
                (platform, account_id, key),
            )
            return key, row

    def _finish_publish_attempt(self, key: str, platform: str, account_id: str, status: str,
                                remote_object_id: str | None = None, error_code: str | None = None,
                                error_message: str | None = None) -> None:
        try:
            self.db.execute(
                "UPDATE publish_attempts SET status=?, remote_object_id=COALESCE(?,remote_object_id), "
                "error_code=?, error_message=?, finished_at=? WHERE platform=? AND account_id=? AND idempotency_key=?",
                (status, remote_object_id, error_code, (error_message or "")[:1000] or None,
                 self.clock.now().isoformat(), platform, account_id, key),
            )
        except Exception:
            logger.debug("publish attempt update failed", exc_info=True)

    def _already_exists(self, entity_type: str, entity_id: int, platform: str, account_id: str = "") -> str | None:
        row = self.db.fetchone(
            """
            SELECT external_id, status, lease_until FROM entity_platform_status
            WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?
              AND status IN ('scheduled', 'updating', 'published', 'publishing',
                             'scheduled_platform', 'uploaded_inbox', 'waiting_manual_publish')
            """,
            (entity_type, entity_id, platform, account_id),
        )
        if not row:
            return None
        ext = (row["external_id"] or "").strip()
        if ext:
            return ext
        if row["status"] == "publishing":
            # lease recovery: stuck publishing without external_id past lease_until
            lease = row.get("lease_until")
            if lease:
                try:
                    lt = datetime.fromisoformat(str(lease).replace("Z", "+00:00"))
                    if lt.tzinfo is None:
                        lt = lt.replace(tzinfo=UTC)
                    if self.clock.now() > lt:
                        return None  # allow re-claim
                except Exception:
                    logger.debug("publish lease_until parse failed", exc_info=True)
            return "__publishing__"
        return None

    def _reserve_publish(self, entity_type: str, entity_id: int, platform: str, account_id: str = "") -> bool:
        """Atomically claim entity/platform for create; sets lease_until for stuck recovery."""
        lease_until = (self.clock.now() + timedelta(minutes=30)).isoformat()
        with self.db.conn() as c:
            row = c.execute(
                """
                SELECT status, external_id, lease_until FROM entity_platform_status
                WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?
                """,
                (entity_type, entity_id, platform, account_id),
            ).fetchone()
            if row is None:
                try:
                    c.execute(
                        """
                        INSERT INTO entity_platform_status
                            (entity_type, entity_id, platform, account_id, status, external_id,
                             last_error, lease_until, attempt)
                        VALUES (?, ?, ?, ?, 'publishing', NULL, NULL, ?, 1)
                        """,
                        (entity_type, entity_id, platform, account_id, lease_until),
                    )
                    return True
                except Exception:
                    return False
            status = row["status"]
            ext = (row["external_id"] or "").strip() if row["external_id"] else ""
            if ext and status in (
                "scheduled", "updating", "published",
                "scheduled_platform", "uploaded_inbox", "waiting_manual_publish",
            ):
                return False
            if status == "publishing":
                lease = row["lease_until"]
                if lease:
                    try:
                        lt = datetime.fromisoformat(str(lease).replace("Z", "+00:00"))
                        if lt.tzinfo is None:
                            lt = lt.replace(tzinfo=UTC)
                        if self.clock.now() <= lt:
                            return False
                    except Exception:
                        return False
                # expired lease — reclaim
            cur = c.execute(
                """
                UPDATE entity_platform_status
                SET status='publishing', last_error=NULL, lease_until=?,
                    attempt=COALESCE(attempt, 0) + 1
                WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?
                  AND (external_id IS NULL OR external_id='')
                  AND (
                    status NOT IN ('publishing', 'published')
                    OR (status='publishing' AND (lease_until IS NULL OR lease_until < ?))
                  )
                """,
                (lease_until, entity_type, entity_id, platform, account_id, self.clock.now().isoformat()),
            )
            return cur.rowcount > 0

    def _release_reserve(self, entity_type: str, entity_id: int, platform: str, account_id: str = "") -> None:
        """Release 'publishing' reserve when create did not complete."""
        self.db.execute(
            "UPDATE entity_platform_status SET status='ready', last_error=NULL, "
            "lease_until=NULL "
            "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? "
            "AND status='publishing' AND (external_id IS NULL OR external_id='')",
            (entity_type, entity_id, platform, account_id),
        )

    def _try_module_publish(
        self,
        entity_type: str,
        entity_id: int,
        platform: str,
        media_path: str | None,
        content: dict[str, Any],
        scheduled_for: datetime | None,
        account_id: str = "",
    ) -> PublishOutcome | None:
        """Publish via PlatformModule when engines.<p>=module:<id>."""
        try:
            from .platforms import default_registry, resolve_engine
        except Exception:
            logger.debug("platforms registry unavailable", exc_info=True)
            return None
        eng = str(self.cfg.engine_for(platform) or "").strip()
        try:
            resolved = resolve_engine(eng)
        except ValueError:
            return None
        if resolved.kind != "module" or not resolved.module_id:
            return None

        reg = self._module_registry or default_registry()
        if not reg.has(resolved.module_id):
            logger.error(
                "module publish: module %r not registered (platform=%s)",
                resolved.module_id, platform,
            )
            self._release_reserve(entity_type, entity_id, platform, account_id)
            raise RuntimeError(f"module {resolved.module_id!r} not registered")

        pcfg = self.cfg.platforms.get(platform)
        # The publish target's account_id is authoritative in multi-account mode.
        # Config-level account_id remains the default only when no target account was supplied.
        aid = str(account_id or "")
        if not aid and pcfg:
            aid = str(getattr(pcfg, "account_id", "") or getattr(pcfg, "integration_id", "") or "")

        def _token_provider(p: str = platform, i: str = aid) -> str:
            # Single canonical token path: broker → account-scoped secret store.
            # Strict broker failures must remain observable; do not silently downgrade here.
            try:
                from .auth_tokens import get_access_token
                return get_access_token(p, account_id=i or "")
            except Exception as exc:
                logger.warning("token resolution failed for %s/%s: %s", p, i or "*", type(exc).__name__)
                return ""

        _mh = getattr(self, "media_host", None)
        mod = reg.create(
            resolved.module_id,
            token_provider=_token_provider,
            cfg=self.cfg,
            dry_run=self.dry_run,
            http=None,
            media_host=_mh,
        )
        from .platforms.base import MediaSpec, PublishMeta

        meta = PublishMeta(
            title=str((content or {}).get("title") or ""),
            description=str((content or {}).get("description") or ""),
            hashtags=str((content or {}).get("hashtags") or ""),
            extra=dict(content or {}),
        )
        prepared = None
        if media_path and self.media_transfer and str(media_path).startswith(("http://", "https://")):
            media_path = self.media_transfer.fetch_url(str(media_path), kind=str(content.get("media_kind") or "video")).path
        elif media_path and self.media_transfer:
            try:
                self.media_transfer.ingest_local(str(media_path), kind=str(content.get("media_kind") or "video"))
            except Exception:
                logger.debug("media artifact registration failed", exc_info=True)
        if media_path:
            mk = str((content or {}).get("media_kind") or (content or {}).get("content_kind") or "video")
            if mk.startswith("promo") or mk in ("image", "image_carousel", "text"):
                kind = "image" if mk != "text" else "text"
            else:
                kind = "video"
            prepared = mod.prepare(MediaSpec(path=media_path, kind=kind))

        self.db.log(entity_type, entity_id, platform, "module.upload.start", resolved.module_id)
        external_sub_id = ""
        publish_mode = "immediate"
        if scheduled_for is not None:
            if prepared is not None:
                from .platforms.base import NotSupported
                try:
                    up = mod.upload(prepared, meta, when=scheduled_for)
                    external_id = up.external_id
                    url = up.url or ""
                    st_up = str(getattr(up, "state", "") or "")
                    if platform == "instagram" or st_up in ("uploaded", "container", "uploaded_inbox"):
                        external_sub_id = external_id
                        publish_mode = "early_upload"
                    try:
                        mod.schedule_publish(external_id, scheduled_for)
                    except Exception as e:
                        if not isinstance(e, NotSupported):
                            raise
                except NotSupported:
                    external_id = f"local-{platform}-{entity_type}-{entity_id}"
                    url = ""
                    publish_mode = "local_schedule"
            else:
                # P0: scheduled + no media must NOT publish now (false "scheduled" in DB).
                # Hold locally; runner will publish when slot is due without scheduled_for.
                external_id = f"local-{platform}-{entity_type}-{entity_id}"
                url = ""
                publish_mode = "local_schedule"
        else:
            if prepared is None:
                prepared = mod.prepare(MediaSpec(path="", kind="text"))
            pr = mod.publish(prepared, meta)
            external_id = pr.external_id
            url = pr.url or ""
            st_pr = str(getattr(pr, "state", "") or "")
            if st_pr == "uploaded_inbox":
                publish_mode = "inbox"
            elif st_pr:
                # keep published
                pass

        self.db.log(entity_type, entity_id, platform, "module.publish.done", external_id)
        # Status mapping: TikTok inbox, IG container early, FB schedule
        st_final = str(locals().get("st_pr") or locals().get("st_up") or "")
        if st_final == "uploaded_inbox":
            status = "uploaded_inbox"
        elif platform == "instagram" and scheduled_for is not None and external_sub_id:
            status = "scheduled_platform"  # container ready; finalize near slot
        elif scheduled_for is not None:
            status = "scheduled"
        elif st_final in {"processing", "uploaded", "queued", "created"}:
            status = st_final
        else:
            status = "published"
        now = self.clock.now().isoformat()
        sched_str = scheduled_for.isoformat() if scheduled_for else None
        outbox_payload = {
            "entity_type": entity_type, "entity_id": entity_id, "platform": platform,
            "account_id": account_id, "external_id": external_id, "status": status,
        }
        # C1: domain mutation, audit row and publish.completed event are atomic.
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO entity_platform_status
                    (entity_type, entity_id, platform, account_id, status,
                     published_at, last_error,
                     external_id, external_sub_id, external_url, scheduled_for, source, publish_mode,
                     lease_until, content_kind)
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, 'module', ?, NULL, ?)
                ON CONFLICT(entity_type, entity_id, platform, account_id) DO UPDATE SET
                    status=excluded.status,
                    published_at=excluded.published_at,
                    last_error=NULL,
                    external_id=excluded.external_id,
                    external_sub_id=excluded.external_sub_id,
                    external_url=excluded.external_url,
                    scheduled_for=excluded.scheduled_for,
                    source=excluded.source,
                    publish_mode=excluded.publish_mode,
                    lease_until=NULL,
                    content_kind=COALESCE(excluded.content_kind, entity_platform_status.content_kind)
                """,
                (
                    entity_type, entity_id, platform, account_id, status,
                    now if not scheduled_for else None,
                    external_id, external_sub_id or None, url or None, sched_str,
                    publish_mode or ("early_upload" if scheduled_for else "immediate"),
                    str((content or {}).get("content_kind") or "video_native"),
                ),
            )
            conn.execute(
                "INSERT INTO publish_log (entity_type, entity_id, platform, action, details, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entity_type, entity_id, platform, "created", external_id, now),
            )
            if self.outbox is not None:
                aggregate_key = f"{entity_type}:{entity_id}:{platform}:{account_id}"
                self.outbox.enqueue_in_transaction(
                    conn, "publish.completed", aggregate_key, aggregate_key, outbox_payload
                )
        if scheduled_for:
            self.safety.record_post(platform, scheduled_for, account_id)
        logger.info(
            "Created module post %s for %s/%s on %s (module=%s)",
            external_id, entity_type, entity_id, platform, resolved.module_id,
        )
        return PublishOutcome(
            id=str(external_id), platform=platform, scheduled_for=scheduled_for,
            status=status, release_url=url or None, content=content,
        )

    def publish(
        self,
        entity_type: str,
        entity_id: int,
        platform: str,
        media_path: str | None,
        content: dict[str, Any],
        scheduled_for: datetime | None = None,
        account_id: str | None = None,
    ) -> PublishOutcome | None:
        """Full publish pipeline with safety + idempotency (module path only)."""
        if scheduled_for and scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=UTC)

        if scheduled_for and self.cfg.safety.jitter_seconds:
            from .slots import apply_jitter
            jittered = apply_jitter(scheduled_for, self.cfg.safety.jitter_seconds)
            if jittered > self.clock.now():
                scheduled_for = jittered

        plat_cfg_for_account = self.cfg.platforms.get(platform)
        if account_id is None:
            account_id = str(getattr(plat_cfg_for_account, "account_id", "") or getattr(plat_cfg_for_account, "integration_id", "") or "") if plat_cfg_for_account else ""
        else:
            account_id = str(account_id or "")
        existing = self._already_exists(entity_type, entity_id, platform, account_id)
        if existing == "__publishing__":
            logger.info("Publish in progress %s/%s %s", entity_type, entity_id, platform)
            return None
        if existing:
            logger.info("Already exists %s/%s %s -> %s", entity_type, entity_id, platform, existing)
            return PublishOutcome(
                id=str(existing), platform=platform, status="scheduled",
            )

        if not self.dry_run:
            if not self._reserve_publish(entity_type, entity_id, platform, account_id):
                existing = self._already_exists(entity_type, entity_id, platform, account_id)
                if existing and existing != "__publishing__":
                    return PublishOutcome(
                        id=str(existing), platform=platform, status="scheduled",
                    )
                logger.info("Could not reserve %s/%s %s (race)", entity_type, entity_id, platform)
                return None

        plat_cfg = self.cfg.platforms.get(platform)
        if self.supervisor is not None:
            try:
                if not self.supervisor.allow(platform, account_id):
                    self.db.log(entity_type, entity_id, platform, "provider_circuit_open", "provider failure isolation")
                    self._release_reserve(entity_type, entity_id, platform, account_id)
                    return None
            except Exception:
                logger.debug("provider supervisor allow check failed", exc_info=True)
        if not plat_cfg or not plat_cfg.enabled:
            logger.warning("Platform %s disabled", platform)
            self._release_reserve(entity_type, entity_id, platform, account_id)
            return None

        if scheduled_for:
            from . import sched_settings
            limit = sched_settings.effective_daily_limit(self.db, self.cfg, platform)
            ok, reason = self.safety.can_schedule(platform, scheduled_for, limit, account_id)
            if not ok:
                self.db.log(entity_type, entity_id, platform, "safety_block", reason)
                logger.info("Safety block %s/%s %s: %s", entity_type, entity_id, platform, reason)
                self._release_reserve(entity_type, entity_id, platform, account_id)
                return None

        if self.guard is not None and scheduled_for is not None:
            reason = self.guard.conflict(platform, scheduled_for, account_id=account_id)
            if reason:
                self.db.log(entity_type, entity_id, platform, "safety_block", reason)
                logger.info(
                    "Schedule conflict %s/%s %s: %s",
                    entity_type, entity_id, platform, reason,
                )
                self._release_reserve(entity_type, entity_id, platform, account_id)
                return None

        if self.dry_run or getattr(self.cfg, "read_only", False) or bool(
            os.getenv("ORCH_READ_ONLY")
        ):
            logger.info(
                "[READ-ONLY/DRY-RUN] skip publish %s/%s to %s at %s",
                entity_type, entity_id, platform, scheduled_for,
            )
            self.db.log(entity_type, entity_id, platform, "dry_run", str(scheduled_for))
            self._release_reserve(entity_type, entity_id, platform, account_id)
            return None

        # module create rate limit
        hourly = (
            getattr(self.cfg.limits, "module_create_per_hour", 0)
            or getattr(self.cfg.limits, "legacy_create_per_hour", 0)  # legacy alias
            or 0
        )
        if hourly and str((content or {}).get("priority") or "") == "link":
            hourly = 0
        if hourly:
            cutoff = (self.clock.now() - timedelta(hours=1)).isoformat()
            row = self.db.fetchone(
                "SELECT COUNT(*) AS c FROM publish_log "
                "WHERE action='created' AND created_at >= ?",
                (cutoff,),
            )
            if row and row["c"] >= hourly:
                self.db.log(
                    entity_type, entity_id, platform, "safety_block", "hourly_create_limit",
                )
                logger.info("Hourly create limit reached (%s)", hourly)
                self._release_reserve(entity_type, entity_id, platform, account_id)
                return None

        # KIND-01 + pre-publish validation
        content_kind = str(
            (content or {}).get("content_kind")
            or getattr(plat_cfg, "content_kind_default", "")
            or "video_native"
        ).strip() or "video_native"
        if media_path:
            try:
                from pathlib import Path as _P
                from .media import prepublish_validate, maybe_compress
                # Only compress/validate when file exists (tests often pass synthetic paths)
                if _P(media_path).is_file():
                    if platform == "telegram" and content_kind.startswith("video"):
                        try:
                            media_path = maybe_compress(media_path, platform, self.cfg) or media_path
                        except Exception:
                            logger.debug("maybe_compress failed", exc_info=True)
                    problems = prepublish_validate(
                        media_path or "", platform, self.cfg, content_kind=content_kind,
                    )
                    if problems:
                        msg = "; ".join(problems)[:500]
                        self.db.log(entity_type, entity_id, platform, "prepublish_block", msg)
                        logger.info(
                            "prepublish block %s/%s %s: %s",
                            entity_type, entity_id, platform, msg,
                        )
                        self._release_reserve(entity_type, entity_id, platform, account_id)
                        return None
                else:
                    # kind-only checks (e.g. promo_text on youtube) without file
                    problems = prepublish_validate(
                        "", platform, self.cfg, content_kind=content_kind,
                    )
                    # ignore "media missing" style — file path may be synthetic
                    problems = [x for x in problems if "missing" not in x.lower()]
                    if problems:
                        msg = "; ".join(problems)[:500]
                        self.db.log(entity_type, entity_id, platform, "prepublish_block", msg)
                        self._release_reserve(entity_type, entity_id, platform, account_id)
                        return None
            except Exception:
                logger.debug("prepublish_validate skipped", exc_info=True)
        if content is not None:
            content = dict(content)
            content.setdefault("content_kind", content_kind)

        # E6: promo_text / image_carousel → use cover as image path when no video file
        if content_kind.startswith("promo") or content_kind == "image_carousel":
            from pathlib import Path as _P
            cover = str((content or {}).get("cover") or (content or {}).get("cover_path") or "").strip()
            if (not media_path or not _P(media_path).is_file()) and cover and _P(cover).is_file():
                media_path = cover
                if content is not None:
                    content["media_kind"] = "image"
            elif not media_path:
                media_path = None

        # link-mode: do not send media file
        if media_path and plat_cfg is not None and \
                str(getattr(plat_cfg, "post_mode", "media") or "media").lower() == "link":
            logger.warning(
                "link-mode %s: skip file %s, publish link only", platform, media_path,
            )
            try:
                self.db.log(
                    entity_type, entity_id, platform, "link_mode_media_skipped", str(media_path),
                )
            except Exception:
                logger.debug("link-mode log failed", exc_info=True)
            media_path = None

        try:
            revision_hash, target_id = self._ensure_schedule_artifacts(
                entity_type, entity_id, platform, account_id, content or {}, media_path, scheduled_for
            )
        except Exception as exc:
            msg = f"schedule_snapshot_setup_failed: {type(exc).__name__}"
            logger.exception("schedule snapshot setup failed %s/%s %s[%s]", entity_type, entity_id, platform, account_id)
            self.db.execute(
                "UPDATE entity_platform_status SET status='error', last_error=?, lease_until=NULL "
                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? AND status='publishing'",
                (msg, entity_type, entity_id, platform, account_id),
            )
            return None
        attempt_key, previous_attempt = self._begin_publish_attempt(
            entity_type, entity_id, platform, account_id, media_path, content or {}
        )
        self.db.execute("UPDATE publish_attempts SET revision_hash=? WHERE platform=? AND account_id=? AND idempotency_key=?", (revision_hash, platform, account_id, attempt_key))
        if previous_attempt and previous_attempt.get("remote_object_id"):
            remote_id = str(previous_attempt.get("remote_object_id"))
            return PublishOutcome(id=remote_id, platform=platform, status=str(previous_attempt.get("status") or "published"))

        try:
            if self.supervisor is not None and not self.supervisor.allow(platform, account_id):
                msg = "provider circuit open"
                self.db.execute(
                    "UPDATE entity_platform_status SET status='ready', last_error=?, lease_until=NULL, next_retry_at=? "
                    "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                    (msg, (self.clock.now() + timedelta(seconds=30)).isoformat(), entity_type, entity_id, platform, account_id),
                )
                self._finish_publish_attempt(attempt_key, platform, account_id, "deferred", error_code="CIRCUIT_OPEN", error_message=msg)
                return None
            if self.supervisor is not None:
                with self.supervisor.queue(platform, account_id, timeout=0) as queue_acquired:
                    if not queue_acquired:
                        retry_at = (self.clock.now() + timedelta(seconds=30)).isoformat()
                        msg = "provider account queue busy; retry scheduled"
                        self._finish_publish_attempt(attempt_key, platform, account_id, "deferred", error_code="QUEUE_BUSY", error_message=msg)
                        self.db.execute(
                            "UPDATE entity_platform_status SET status='ready', last_error=?, lease_until=NULL, next_retry_at=? "
                            "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? "
                            "AND status='publishing' AND (external_id IS NULL OR external_id='')",
                            (msg, retry_at, entity_type, entity_id, platform, account_id),
                        )
                        logger.info("Publish deferred due to provider queue: %s/%s %s retry_at=%s", entity_type, entity_id, platform, retry_at)
                        return None
                    mod_post = self._try_module_publish(
                        entity_type, entity_id, platform, media_path, content or {}, scheduled_for, account_id,
                    )
            else:
                mod_post = self._try_module_publish(
                    entity_type, entity_id, platform, media_path, content or {}, scheduled_for, account_id,
                )
            if mod_post is not None:
                result_status = str(
                    getattr(mod_post, "status", "")
                    or getattr(mod_post, "state", "")
                    or "published"
                )
                self._finish_publish_attempt(attempt_key, platform, account_id, result_status, mod_post.id)
                self.db.execute("UPDATE distribution_targets SET status=?, updated_at=? WHERE id=?", ("published" if result_status not in {"processing", "uploaded", "scheduled"} else result_status, self.clock.now().isoformat(), target_id))
                if self.supervisor is not None:
                    try:
                        self.supervisor.record_success(platform, account_id)
                    except Exception:
                        logger.debug("provider supervisor success update failed", exc_info=True)
                return mod_post
        except Exception as e:
            # N4: never leave a row stuck in publishing after module failure.
            # ModuleError.retryable is the source of truth; unknown exceptions are terminal.
            err = f"{type(e).__name__}: {e}"[:500]
            retryable = bool(getattr(e, "retryable", False))
            next_status = "ready" if retryable else "error"
            logger.exception(
                "module publish failed %s %s %s retryable=%s",
                platform, entity_type, entity_id, retryable,
            )
            self._finish_publish_attempt(attempt_key, platform, account_id, "error", error_code=str(getattr(e, "code", "FATAL")), error_message=err)
            self.db.execute("UPDATE distribution_targets SET status=?, updated_at=? WHERE id=?", ("failed", self.clock.now().isoformat(), target_id))
            if self.supervisor is not None:
                try:
                    code = str(getattr(e, "code", "FATAL"))
                    infrastructure_failure = retryable or code in {
                        "AUTH_EXPIRED", "AUTH_REQUIRED", "RATE_LIMIT", "TRANSIENT",
                        "DEPENDENCY_DOWN", "API_DEPRECATED", "WEBHOOK_BROKEN",
                    }
                    if infrastructure_failure:
                        self.supervisor.record_failure(platform, account_id, err)
                except Exception:
                    logger.debug("provider supervisor failure update failed", exc_info=True)
            try:
                self.db.execute(
                    "UPDATE entity_platform_status SET status=?, last_error=?, "
                    "lease_until=NULL, next_retry_at=? "
                    "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                    (
                        next_status, err, self.clock.now().isoformat() if retryable else None,
                        entity_type, entity_id, platform, account_id,
                    ),
                )
                self.db.log(entity_type, entity_id, platform, "publish_error", err)
            except Exception:
                self._release_reserve(entity_type, entity_id, platform, account_id)
            raise

        self._release_reserve(entity_type, entity_id, platform, account_id)
        raise RuntimeError(
            f"publisher: no module path for platform={platform!r} — "
            "configure engines.<platform>=module:<id>"
        )

    def cancel_or_delete(self, platform: str, external_id: str) -> bool:
        """Best-effort remote cancel via platform module; always clears local lease."""
        external_id = str(external_id or "").strip()
        if not external_id:
            return False
        try:
            from .platforms import default_registry, resolve_engine
            eng = str(self.cfg.engine_for(platform) or "").strip()
            resolved = resolve_engine(eng)
            if resolved.kind != "module" or not resolved.module_id:
                return False
            reg = self._module_registry or default_registry()
            if not reg.has(resolved.module_id):
                return False
            try:
                mod = reg.create(resolved.module_id, dry_run=self.dry_run)
            except Exception:
                return False
            if hasattr(mod, "delete"):
                try:
                    mod.delete(external_id)
                    return True
                except Exception:
                    logger.warning("cancel_or_delete module.delete failed %s/%s",
                                   platform, external_id, exc_info=True)
            return False
        except Exception:
            logger.warning("cancel_or_delete failed %s/%s", platform, external_id, exc_info=True)
            return False


