from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from .clock import Clock
from .config import AppConfig
from .db import Database
from .media import make_media
from .postiz import PostizClient, PostizPost
from .safety import SafetyChecker

logger = logging.getLogger(__name__)


class Publisher:
    def __init__(
        self,
        db: Database,
        cfg: AppConfig,
        postiz: PostizClient,
        safety: SafetyChecker,
        clock: Clock,
        dry_run: bool = False,
        guard: Any = None,
        broker: Any = None,
    ):
        self.db = db
        self.cfg = cfg
        self.postiz = postiz
        self.safety = safety
        self.clock = clock
        self.dry_run = dry_run
        self.guard = guard
        self.broker = broker

    def _already_exists(self, entity_type: str, entity_id: int, platform: str) -> str | None:
        row = self.db.fetchone(
            """
            SELECT postiz_post_id, status FROM entity_platform_status
            WHERE entity_type=? AND entity_id=? AND platform=?
              AND status IN ('scheduled', 'updating', 'published', 'publishing')
            """,
            (entity_type, entity_id, platform),
        )
        if not row:
            return None
        pid = row["postiz_post_id"]
        if pid:
            return pid
        if row["status"] == "publishing":
            return "__publishing__"
        return None

    def _reserve_publish(self, entity_type: str, entity_id: int, platform: str) -> bool:
        """Atomically claim entity/platform for create (R1')."""
        with self.db.conn() as c:
            row = c.execute(
                """
                SELECT status, postiz_post_id FROM entity_platform_status
                WHERE entity_type=? AND entity_id=? AND platform=?
                """,
                (entity_type, entity_id, platform),
            ).fetchone()
            if row is None:
                try:
                    c.execute(
                        """
                        INSERT INTO entity_platform_status
                            (entity_type, entity_id, platform, status, postiz_post_id, last_error)
                        VALUES (?, ?, ?, 'publishing', NULL, NULL)
                        """,
                        (entity_type, entity_id, platform),
                    )
                    return True
                except Exception:
                    return False
            status = row["status"]
            pid = row["postiz_post_id"]
            # Live posts with an id are taken
            if pid and status in ("scheduled", "updating", "published"):
                return False
            # Another worker already publishing
            if status == "publishing":
                return False
            # refresh path: updating/ready/error without post id may be claimed
            if status in ("scheduled", "published") and pid:
                return False
            cur = c.execute(
                """
                UPDATE entity_platform_status
                SET status='publishing', last_error=NULL
                WHERE entity_type=? AND entity_id=? AND platform=?
                  AND postiz_post_id IS NULL
                  AND status NOT IN ('publishing', 'published')
                  AND (status NOT IN ('scheduled') OR postiz_post_id IS NULL)
                """,
                (entity_type, entity_id, platform),
            )
            return cur.rowcount > 0

    def publish(
        self,
        entity_type: str,
        entity_id: int,
        platform: str,
        media_path: str | None,
        content: dict[str, Any],
        scheduled_for: datetime | None = None,
    ) -> PostizPost | None:
        """Full publish pipeline with safety + idempotency."""
        if scheduled_for and scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=UTC)

        # jitter
        if scheduled_for and self.cfg.safety.jitter_seconds:
            from .slots import apply_jitter
            jittered = apply_jitter(scheduled_for, self.cfg.safety.jitter_seconds)
            if jittered > self.clock.now():
                scheduled_for = jittered

        # 1. Idempotency first (prevent self min_interval block)
        existing = self._already_exists(entity_type, entity_id, platform)
        if existing == "__publishing__":
            logger.info("Publish in progress %s/%s %s", entity_type, entity_id, platform)
            return None
        if existing:
            logger.info("Already exists %s/%s %s -> %s", entity_type, entity_id, platform, existing)
            return self.postiz.get_post(existing)

        # 1b. Reserve slot so parallel publish cannot create a second Postiz post (R1')
        if not self.dry_run:
            if not self._reserve_publish(entity_type, entity_id, platform):
                existing = self._already_exists(entity_type, entity_id, platform)
                if existing and existing != "__publishing__":
                    return self.postiz.get_post(existing)
                logger.info("Could not reserve %s/%s %s (race)", entity_type, entity_id, platform)
                return None

        # 2. Safety
        plat_cfg = self.cfg.platforms.get(platform)
        if not plat_cfg or not plat_cfg.enabled:
            logger.warning("Platform %s disabled", platform)
            return None

        if scheduled_for:
            from . import sched_settings
            limit = sched_settings.effective_daily_limit(self.db, self.cfg, platform)
            ok, reason = self.safety.can_schedule(
                platform, scheduled_for, limit
            )
            if not ok:
                self.db.log(entity_type, entity_id, platform, "safety_block", reason)
                logger.info("Safety block %s/%s %s: %s", entity_type, entity_id, platform, reason)
                return None

        if self.guard is not None and scheduled_for is not None:
            reason = self.guard.conflict(platform, scheduled_for)
            if reason:
                self.db.log(entity_type, entity_id, platform, "safety_block", reason)
                logger.info("Schedule conflict %s/%s %s: %s",
                            entity_type, entity_id, platform, reason)
                return None

        if self.dry_run or getattr(self.cfg, "read_only", False) or bool(
            __import__("os").getenv("ORCH_READ_ONLY")
        ):
            logger.info("[READ-ONLY/DRY-RUN] skip publish %s/%s to %s at %s",
                        entity_type, entity_id, platform, scheduled_for)
            self.db.log(entity_type, entity_id, platform, "dry_run", str(scheduled_for))
            return None

        # Postiz hourly create limit (config: limits.postiz_create_per_hour)
        hourly = getattr(self.cfg.limits, "postiz_create_per_hour", 0) or 0
        if hourly and str((content or {}).get("priority") or "") == "link":
            hourly = 0  # пост-ссылка после премьеры не должен ждать час
        if hourly:
            cutoff = (self.clock.now() - timedelta(hours=1)).isoformat()
            row = self.db.fetchone(
                "SELECT COUNT(*) AS c FROM publish_log "
                "WHERE action='created' AND created_at >= ? "
                "AND EXISTS (SELECT 1 FROM entity_platform_status eps "
                "  WHERE eps.entity_type=publish_log.entity_type "
                "    AND eps.entity_id=publish_log.entity_id "
                "    AND eps.platform=publish_log.platform)",
                (cutoff,),
            )
            if row and row["c"] >= hourly:
                self.db.log(entity_type, entity_id, platform, "safety_block", "hourly_create_limit")
                logger.info("Hourly create limit reached (%s)", hourly)
                return None

        # 3. Upload (для постов-ссылок медиа нет)
        pcfg = self.cfg.platforms.get(platform)
        if pcfg and getattr(pcfg, "integration_id", None):
            content = {**content, "integration_id": pcfg.integration_id}
        cover_path = str(content.get("cover") or "").strip()
        if platform == "youtube" and cover_path:
            try:
                cref = self.postiz.upload_media(cover_path, platform)
                content = {**content,
                           "settings": {"thumbnail": {"id": cref.id, "path": cref.path}}}
            except Exception:
                logger.warning("cover upload failed: %s", cover_path, exc_info=True)

        media = None
        if media_path:
            try:
                # D2: Telegram Bot API не принимает файлы >50 МБ — ловим до создания поста
                if platform == "telegram" and media_path:
                    try:
                        import os as _os
                        _mb = _os.path.getsize(media_path) / (1024 * 1024)
                    except OSError:
                        _mb = 0
                    if _mb > 50 and not int(getattr(self.cfg.media, "telegram_max_mb", 0) or 0):
                        raise RuntimeError(
                            f"telegram: файл {_mb:.0f} МБ > лимита Bot API 50 МБ "
                            "(включите media.telegram_max_mb для сжатия или используйте link-режим)"
                        )
                media = make_media(media_path, platform, self.cfg, self.postiz, self.broker)
            except Exception as e:
                self.db.execute(
                    "UPDATE entity_platform_status SET status='error', last_error=? "
                    "WHERE entity_type=? AND entity_id=? AND platform=?",
                    (str(e), entity_type, entity_id, platform),
                )
                self.db.log(entity_type, entity_id, platform, "upload_fail", str(e))
                raise

        # 4. CREATE with retries
        import os
        delays = (0, 0, 0, 0) if os.getenv("ORCH_FAST_RETRY") else (0, 2, 6, 18)
        post: PostizPost | None = None
        last_err: Exception | None = None
        for attempt, delay in enumerate(delays, 1):
            if delay:
                import time
                time.sleep(delay)
            try:
                post = self.postiz.create_post(
                    platform=platform,
                    media=media,
                    content=content,
                    scheduled_for=scheduled_for,
                )
                break
            except Exception as e:
                last_err = e
                logger.warning("CREATE attempt %s failed: %s", attempt, e)
                from .postiz_http import is_safe_retry
                if not is_safe_retry(e):
                    logger.warning("CREATE не повторяем (возможен дубликат): %s", type(e).__name__)
                    break

        if post is None:
            err_msg = str(last_err) if last_err else "create_failed_no_post"
            self.db.execute(
                "UPDATE entity_platform_status SET status='error', last_error=? "
                "WHERE entity_type=? AND entity_id=? AND platform=?",
                (err_msg, entity_type, entity_id, platform),
            )
            self.db.log(entity_type, entity_id, platform, "create_fail", err_msg)
            # R5: track orphan media (uploaded but post not created) for ops visibility
            try:
                orphans = []
                if hasattr(self.postiz, "orphan_media_ids"):
                    orphans = list(self.postiz.orphan_media_ids())
                if orphans:
                    self.db.log(entity_type, entity_id, platform, "orphan_media", ",".join(str(x) for x in orphans))
                    logger.warning("Orphan media after create fail: %s", orphans)
            except Exception:
                logger.debug("orphan media log failed", exc_info=True)
            if last_err is not None:
                raise last_err
            raise RuntimeError(err_msg)

        # 5. Save
        status = "scheduled" if scheduled_for else "published"
        now = self.clock.now().isoformat()
        sched_str = scheduled_for.isoformat() if scheduled_for else None
        self.db.execute(
            """
            INSERT INTO entity_platform_status
                (entity_type, entity_id, platform, status, postiz_post_id,
                 postiz_scheduled_for, published_at, last_error)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(entity_type, entity_id, platform) DO UPDATE SET
                status=excluded.status,
                postiz_post_id=excluded.postiz_post_id,
                postiz_scheduled_for=excluded.postiz_scheduled_for,
                published_at=excluded.published_at,
                last_error=NULL
            """,
            (entity_type, entity_id, platform, status, post.id, sched_str,
             now if not scheduled_for else None),
        )
        if scheduled_for:
            self.safety.record_post(platform, scheduled_for)
        self.db.log(entity_type, entity_id, platform, "created", post.id)
        logger.info("Created %s for %s/%s on %s", post.id, entity_type, entity_id, platform)
        return post
