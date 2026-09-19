from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from .clock import Clock
from .config import AppConfig
from .db import Database
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
    ):
        self.db = db
        self.cfg = cfg
        self.postiz = postiz
        self.safety = safety
        self.clock = clock
        self.dry_run = dry_run

    def _idempotency_key(self, entity_type: str, entity_id: int, platform: str,
                         scheduled_for: datetime | None) -> str:
        ts = scheduled_for.isoformat() if scheduled_for else "now"
        return f"{entity_type}:{entity_id}:{platform}:{ts}"

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
            scheduled_for = apply_jitter(scheduled_for, self.cfg.safety.jitter_seconds)

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

        if self.dry_run:
            logger.info("[DRY-RUN] Would publish %s/%s to %s at %s",
                        entity_type, entity_id, platform, scheduled_for)
            self.db.log(entity_type, entity_id, platform, "dry_run", str(scheduled_for))
            return None

        # 3. Upload
        pcfg = self.cfg.platforms.get(platform)
        if pcfg and getattr(pcfg, "integration_id", None):
            content = {**content, "integration_id": pcfg.integration_id}
        try:
            media = self.postiz.upload_media(media_path, platform)
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
