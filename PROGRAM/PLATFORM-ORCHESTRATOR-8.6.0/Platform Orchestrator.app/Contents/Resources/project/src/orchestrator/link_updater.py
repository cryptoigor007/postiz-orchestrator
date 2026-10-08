from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from .clock import Clock
from .config import AppConfig
from .db import Database
from .telegram_bot import TelegramNotifier

logger = logging.getLogger(__name__)


class LinkUpdater:
    """Update release_url / external_url on EPS; module-only (no platform client)."""

    def __init__(
        self,
        db: Database,
        cfg: AppConfig,
        clock: Clock,
        tg: TelegramNotifier,
    ):
        self.db = db
        self.cfg = cfg
        self.clock = clock
        self.tg = tg

    def check_missing_urls(self) -> int:
        """Find published long videos without release_url past timeout → dialog or default."""
        timeout = self.cfg.link_update.release_url_timeout_min
        cutoff = (self.clock.now() - timedelta(minutes=timeout)).isoformat()
        rows = self.db.fetchall(
            """
            SELECT entity_id, platform, account_id, published_at FROM entity_platform_status
            WHERE entity_type='long_video' AND status='published'
              AND (release_url IS NULL OR release_url='')
              AND (external_url IS NULL OR external_url='')
              AND published_at IS NOT NULL AND published_at < ?
            """,
            (cutoff,),
        )
        acted = 0
        for r in rows:
            default = self.cfg.link_update.missing_url_default_action
            if default == "post_without_link":
                self.db.execute(
                    "UPDATE entity_platform_status SET link_updated_at=? "
                    "WHERE entity_type='long_video' AND entity_id=? AND platform=? AND account_id=?",
                    (self.clock.now().isoformat(), r["entity_id"], r["platform"], r.get("account_id") or ""),
                )
                self.db.execute(
                    "UPDATE entity_platform_status SET status='published' "
                    "WHERE entity_type='long_video' AND entity_id=? AND platform=? AND account_id=? "
                    "AND status='published'",
                    (r["entity_id"], r["platform"], r.get("account_id") or ""),
                )
                acted += 1
            elif default == "refresh":
                self.db.execute(
                    "UPDATE entity_platform_status SET link_updated_at=? "
                    "WHERE entity_type='long_video' AND entity_id=? AND platform=? AND account_id=?",
                    (self.clock.now().isoformat(), r["entity_id"], r["platform"], r.get("account_id") or ""),
                )
                acted += 1
            else:
                self.tg.ask_missing_url(r["entity_id"], r["platform"], account_id=str(r.get("account_id") or ""))
                acted += 1
        return acted

    def force_update(
        self,
        entity_id: int,
        platform: str,
        new_url: str,
        scheduler: Any = None,
        entity_type: str | None = None,
        account_id: str = "",
    ) -> bool:
        """Set release_url + external_url and drive refresh path."""
        if not (new_url.startswith("http://") or new_url.startswith("https://")):
            return False
        if entity_type:
            if not account_id:
                matches = self.db.fetchall(
                    "SELECT DISTINCT account_id FROM entity_platform_status "
                    "WHERE entity_type=? AND entity_id=? AND platform=?",
                    (entity_type, entity_id, platform),
                )
                if len(matches) != 1:
                    return False
                account_id = str(matches[0].get("account_id") or "")
            row = self.db.fetchone(
                "SELECT entity_type, release_url, external_id, external_url "
                "FROM entity_platform_status "
                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                (entity_type, entity_id, platform, account_id),
            )
        else:
            row = self.db.fetchone(
                "SELECT entity_type, account_id, release_url, external_id, external_url "
                "FROM entity_platform_status "
                "WHERE entity_id=? AND platform=? " + ("AND account_id=? " if account_id else "") +
                "ORDER BY "
                "  CASE WHEN release_url IS NULL OR release_url='' THEN 0 ELSE 1 END, "
                "  CASE entity_type WHEN 'long_video' THEN 0 ELSE 1 END "
                "LIMIT 1",
                (entity_id, platform, account_id) if account_id else (entity_id, platform),
            )
        if not row:
            return False
        entity_type = row["entity_type"] or "long_video"
        self.db.execute(
            "UPDATE entity_platform_status SET release_url=?, external_url=?, "
            "link_updated_at=? "
            "WHERE entity_id=? AND platform=? AND entity_type=? AND account_id=?",
            (
                new_url, new_url, self.clock.now().isoformat(),
                entity_id, platform, entity_type, account_id,
            ),
        )
        self.db.log(entity_type, entity_id, platform, "force_link_update", new_url)
        if scheduler is not None:
            if entity_type == "long_video":
                try:
                    self.refresh_thematic_after_url(entity_id, platform, scheduler, account_id=account_id)
                except Exception:
                    logger.exception("force_update thematic refresh failed")
            try:
                if hasattr(scheduler, "refresh_telegram_links"):
                    scheduler.refresh_telegram_links()
            except Exception:
                logger.exception("force_update telegram refresh failed")
        return True

    def refresh_thematic_after_url(
        self, parent_id: int, platform: str, scheduler: Any, account_id: str = "",
    ) -> int:
        """When release_url appears: reschedule thematic shorts with link template."""
        parent = self.db.fetchone(
            "SELECT release_url, external_url, account_id FROM entity_platform_status "
            "WHERE entity_type='long_video' AND entity_id=? AND platform=? "
            "AND account_id=? AND status='published'",
            (parent_id, platform, account_id),
        )
        if not parent:
            return 0
        url = parent.get("release_url") or parent.get("external_url") or ""
        if not url:
            return 0
        template = self.cfg.description_templates.get(
            "thematic_short", "{description}\n\n▶ Полное видео: {link}"
        )
        rows = self.db.fetchall(
            """
            SELECT eps.entity_id, eps.account_id, eps.external_id, eps.scheduled_for,
                   s.video_path, s.title_text, s.description_text, s.hashtags_text
            FROM entity_platform_status eps
            JOIN shorts s ON s.id = eps.entity_id
            WHERE eps.entity_type='short' AND eps.platform=?
              AND s.parent_video_id=?
              AND eps.account_id=?
              AND eps.status IN ('scheduled', 'updating')
              AND eps.external_id IS NOT NULL AND eps.external_id != ''
            """,
            (platform, parent_id, account_id),
        )
        updated = 0
        for r in rows:
            desc = template.format(description=r["description_text"] or "", link=url)
            content = {
                "title": r["title_text"] or "",
                "description": desc,
                "hashtags": r["hashtags_text"] or "",
            }
            sched = None
            if r["scheduled_for"]:
                try:
                    sched = datetime.fromisoformat(
                        str(r["scheduled_for"]).replace("Z", "+00:00")
                    )
                except Exception:
                    sched = None
            try:
                old_id = r["external_id"]
                self.db.execute(
                    "UPDATE entity_platform_status SET external_id=NULL, status='ready' "
                    "WHERE entity_type='short' AND entity_id=? AND platform=? AND account_id=?",
                    (r["entity_id"], platform, r.get("account_id") or ""),
                )
                pub = getattr(scheduler, "publisher", None)
                if pub is None:
                    continue
                try:
                    post = pub.publish(
                        "short", r["entity_id"], platform,
                        r["video_path"], content, sched, account_id=str(r.get("account_id") or ""),
                    )
                except Exception:
                    post = None
                    logger.exception("refresh thematic publish failed %s", r["entity_id"])
                if post:
                    # best-effort delete old platform copy via module
                    if old_id and hasattr(pub, "_try_module_delete"):
                        try:
                            pub._try_module_delete(platform, old_id)  # type: ignore[attr-defined]
                        except Exception:
                            logger.debug("old post delete skipped %s", old_id, exc_info=True)
                    updated += 1
                elif old_id:
                    self.db.execute(
                        "UPDATE entity_platform_status SET external_id=?, status='scheduled', "
                        "last_error='refresh_failed' WHERE entity_type='short' AND entity_id=? "
                        "AND platform=? AND account_id=?",
                        (old_id, r["entity_id"], platform, r.get("account_id") or ""),
                    )
            except Exception:
                logger.exception("refresh thematic short %s", r["entity_id"])
        return updated
