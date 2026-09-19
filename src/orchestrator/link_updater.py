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
                # mark so thematic can proceed without link
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

    def force_update(self, entity_id: int, platform: str, new_url: str) -> bool:
        if not (new_url.startswith("http://") or new_url.startswith("https://")):
            return False
        row = self.db.fetchone(
            "SELECT postiz_post_id FROM entity_platform_status "
            "WHERE entity_type='long_video' AND entity_id=? AND platform=?",
            (entity_id, platform),
        )
        if not row:
            return False
        self.db.execute(
            "UPDATE entity_platform_status SET release_url=?, link_updated_at=? "
            "WHERE entity_type='long_video' AND entity_id=? AND platform=?",
            (new_url, self.clock.now().isoformat(), entity_id, platform),
        )
        self.db.log("long_video", entity_id, platform, "force_link_update", new_url)
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
