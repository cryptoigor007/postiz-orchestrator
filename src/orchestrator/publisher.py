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
            SELECT postiz_post_id FROM entity_platform_status
            WHERE entity_type=? AND entity_id=? AND platform=?
              AND status IN ('scheduled', 'updating', 'published')
              AND postiz_post_id IS NOT NULL
            """,
            (entity_type, entity_id, platform),
        )
        return row["postiz_post_id"] if row else None

    def publish(
        self,
        entity_type: str,
        entity_id: int,
        platform: str,
        media_path: str,
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
        if existing:
            logger.info("Already exists %s/%s %s -> %s", entity_type, entity_id, platform, existing)
            return self.postiz.get_post(existing)

        # 2. Safety
        plat_cfg = self.cfg.platforms.get(platform)
        if not plat_cfg or not plat_cfg.enabled:
            logger.warning("Platform %s disabled", platform)
            return None

        if scheduled_for:
            ok, reason = self.safety.can_schedule(
                platform, scheduled_for, plat_cfg.daily_limit
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

        if self.dry_run:
            logger.info("[DRY-RUN] Would publish %s/%s to %s at %s",
                        entity_type, entity_id, platform, scheduled_for)
            self.db.log(entity_type, entity_id, platform, "dry_run", str(scheduled_for))
            return None

        # Postiz hourly create limit (config: limits.postiz_create_per_hour)
        hourly = getattr(self.cfg.limits, "postiz_create_per_hour", 0) or 0
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

        # 3. Upload
        pcfg = self.cfg.platforms.get(platform)
        if pcfg and getattr(pcfg, "integration_id", None):
            content = {**content, "integration_id": pcfg.integration_id}
        try:
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
        last_err = None
        import os
        delays = (0, 0, 0, 0) if os.getenv("ORCH_FAST_RETRY") else (0, 2, 6, 18)
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
        else:
            self.db.execute(
                "UPDATE entity_platform_status SET status='error', last_error=? "
                "WHERE entity_type=? AND entity_id=? AND platform=?",
                (str(last_err), entity_type, entity_id, platform),
            )
            self.db.log(entity_type, entity_id, platform, "create_fail", str(last_err))
            raise last_err  # type: ignore

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
