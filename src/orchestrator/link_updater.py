from __future__ import annotations

import logging
from datetime import datetime, timedelta

from .clock import Clock
from .config import AppConfig
from .db import Database
from .postiz import PostizClient
from .telegram_bot import TelegramNotifier

logger = logging.getLogger(__name__)


class LinkUpdater:
    def __init__(
        self,
        db: Database,
        cfg: AppConfig,
        postiz: PostizClient,
        clock: Clock,
        tg: TelegramNotifier,
    ):
        self.db = db
        self.cfg = cfg
        self.postiz = postiz
        self.clock = clock
        self.tg = tg

    def check_missing_urls(self) -> int:
        """Find published long videos without release_url past timeout → dialog or default."""
        timeout = self.cfg.link_update.release_url_timeout_min
        cutoff = (self.clock.now() - timedelta(minutes=timeout)).isoformat()
        rows = self.db.fetchall(
            """
            SELECT entity_id, platform, published_at FROM entity_platform_status
            WHERE entity_type='long_video' AND status='published'
              AND (release_url IS NULL OR release_url='')
              AND published_at IS NOT NULL AND published_at < ?
            """,
            (cutoff,),
        )
        acted = 0
        for r in rows:
            default = self.cfg.link_update.missing_url_default_action
            if default == "post_without_link":
                # L45: mark so thematic can proceed with placeholder template
                self.db.execute(
                    "UPDATE entity_platform_status SET link_updated_at=? "
                    "WHERE entity_type='long_video' AND entity_id=? AND platform=?",
                    (self.clock.now().isoformat(), r["entity_id"], r["platform"]),
                )
                # Ensure status stays published so schedule_thematic can pick it up
                self.db.execute(
                    "UPDATE entity_platform_status SET status='published' "
                    "WHERE entity_type='long_video' AND entity_id=? AND platform=? "
                    "AND status='published'",
                    (r["entity_id"], r["platform"]),
                )
                acted += 1
            elif default == "refresh":
                # L45: attempt refresh path even without URL (placeholder) via thematic schedule
                self.db.execute(
                    "UPDATE entity_platform_status SET link_updated_at=? "
                    "WHERE entity_type='long_video' AND entity_id=? AND platform=?",
                    (self.clock.now().isoformat(), r["entity_id"], r["platform"]),
                )
                acted += 1
            else:
                self.tg.ask_missing_url(r["entity_id"], r["platform"])
                acted += 1
        return acted

    def force_update(
        self,
        entity_id: int,
        platform: str,
        new_url: str,
        scheduler=None,
        entity_type: str | None = None,
    ) -> bool:
        """Set release_url for any entity_type and drive refresh path (L44).

        Работает для short, long_video и любого другого entity_type в
        entity_platform_status (раньше — только long_video).
        Если entity_type не задан, а под (entity_id, platform) подходит несколько
        записей (id у short и long_video независимы и могут совпадать), берётся
        запись без release_url — её обычно и чинят; при равенстве — long_video.
        """
        if not (new_url.startswith("http://") or new_url.startswith("https://")):
            return False
        if entity_type:
            row = self.db.fetchone(
                "SELECT entity_type, postiz_post_id, release_url "
                "FROM entity_platform_status "
                "WHERE entity_type=? AND entity_id=? AND platform=?",
                (entity_type, entity_id, platform),
            )
        else:
            row = self.db.fetchone(
                "SELECT entity_type, postiz_post_id, release_url "
                "FROM entity_platform_status "
                "WHERE entity_id=? AND platform=? "
                "ORDER BY "
                "  CASE WHEN release_url IS NULL OR release_url='' THEN 0 ELSE 1 END, "
                "  CASE entity_type WHEN 'long_video' THEN 0 ELSE 1 END "
                "LIMIT 1",
                (entity_id, platform),
            )
        if not row:
            return False
        entity_type = row["entity_type"] or "long_video"
        self.db.execute(
            "UPDATE entity_platform_status SET release_url=?, link_updated_at=? "
            "WHERE entity_id=? AND platform=? AND entity_type=?",
            (new_url, self.clock.now().isoformat(), entity_id, platform, entity_type),
        )
        self.db.log(entity_type, entity_id, platform, "force_link_update", new_url)
        # L44: refresh thematic descriptions + telegram links when URL appears
        if scheduler is not None:
            if entity_type == "long_video":  # тематические шортсы есть только у длинных
                try:
                    self.refresh_thematic_after_url(entity_id, platform, scheduler)
                except Exception:
                    logger.exception("force_update thematic refresh failed")
            try:
                if hasattr(scheduler, "refresh_telegram_links"):
                    scheduler.refresh_telegram_links()
            except Exception:
                logger.exception("force_update telegram refresh failed")
        return True


    def refresh_thematic_after_url(self, parent_id: int, platform: str, scheduler) -> int:
        """When release_url appears: reschedule thematic with link template.
        For already scheduled shorts — create new post with link, delete old.
        """
        parent = self.db.fetchone(
            "SELECT release_url FROM entity_platform_status "
            "WHERE entity_type='long_video' AND entity_id=? AND platform=? AND status='published'",
            (parent_id, platform),
        )
        if not parent or not parent.get("release_url"):
            return 0
        url = parent["release_url"]
        template = self.cfg.description_templates.get(
            "thematic_short", "{description}\n\n▶ Полное видео: {link}"
        )
        rows = self.db.fetchall(
            """
            SELECT eps.entity_id, eps.postiz_post_id, eps.postiz_scheduled_for,
                   s.video_path, s.title_text, s.description_text, s.hashtags_text
            FROM entity_platform_status eps
            JOIN shorts s ON s.id = eps.entity_id
            WHERE eps.entity_type='short' AND eps.platform=?
              AND s.parent_video_id=?
              AND eps.status IN ('scheduled', 'updating')
              AND eps.postiz_post_id IS NOT NULL
            """,
            (platform, parent_id),
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
            if r["postiz_scheduled_for"]:
                sched = datetime.fromisoformat(r["postiz_scheduled_for"])
            try:
                old_id = r["postiz_post_id"]
                # clear old status to allow re-create
                self.db.execute(
                    "UPDATE entity_platform_status SET postiz_post_id=NULL, status='ready' "
                    "WHERE entity_type='short' AND entity_id=? AND platform=?",
                    (r["entity_id"], platform),
                )
                pub = getattr(scheduler, "publisher", None)
                if pub is None:
                    continue
                try:
                    post = pub.publish(
                        "short", r["entity_id"], platform,
                        r["video_path"], content, sched,
                    )
                except Exception:
                    post = None
                    logger.exception("refresh thematic publish failed %s", r["entity_id"])
                if post:
                    if old_id:
                        try:
                            self.postiz.delete_post(old_id)
                        except Exception:
                            logger.warning("Failed to delete old post %s", old_id)
                    updated += 1
                elif old_id:
                    # откат: вернуть старую привязку, чтобы не потерять пост
                    self.db.execute(
                        "UPDATE entity_platform_status SET postiz_post_id=?, status='scheduled', "
                        "last_error='refresh_failed' WHERE entity_type='short' AND entity_id=? "
                        "AND platform=?",
                        (old_id, r["entity_id"], platform),
                    )
            except Exception:
                logger.exception("refresh thematic short %s", r["entity_id"])
        return updated
