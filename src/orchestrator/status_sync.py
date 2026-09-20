from __future__ import annotations

import logging
from datetime import UTC, datetime

from .clock import Clock
from .config import AppConfig
from .db import Database
from .postiz import PostizClient

logger = logging.getLogger(__name__)


class StatusSync:
    def __init__(self, db: Database, postiz: PostizClient, clock: Clock, cfg: AppConfig):
        self.db = db
        self.postiz = postiz
        self.clock = clock
        self.cfg = cfg

    def sync(self, fresh_only: bool = False) -> int:
        """Pull status from Postiz for known scheduled/updating posts.
        If fresh_only — only posts scheduled within confirm_published_interval window around now.
        """
        sql = """
            SELECT entity_type, entity_id, platform, postiz_post_id, status, postiz_scheduled_for
            FROM entity_platform_status
            WHERE postiz_post_id IS NOT NULL
              AND status IN ('scheduled', 'updating')
        """
        rows = self.db.fetchall(sql)
        if fresh_only:
            window = self.cfg.confirm_published_interval_sec
            now = self.clock.now()
            filtered = []
            for r in rows:
                if not r.get("postiz_scheduled_for"):
                    filtered.append(r)
                    continue
                try:
                    st = datetime.fromisoformat(r["postiz_scheduled_for"])
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
                post = self.postiz.get_post(row["postiz_post_id"])
            except Exception:
                logger.warning("get_post failed for %s (skip)", row["postiz_post_id"],
                               exc_info=True)
                continue
            if not post:
                self.db.execute(
                    "UPDATE entity_platform_status SET status='error', last_error='missing_in_postiz' "
                    "WHERE entity_type=? AND entity_id=? AND platform=?",
                    (row["entity_type"], row["entity_id"], row["platform"]),
                )
                updated += 1
                continue
            if post.status == "error" and row["status"] != "error":
                self.db.execute(
                    "UPDATE entity_platform_status SET status='error', "
                    "last_error='postiz_error' WHERE entity_type=? AND entity_id=? "
                    "AND platform=?",
                    (row["entity_type"], row["entity_id"], row["platform"]),
                )
                updated += 1
                continue
            if post.status == "published" and row["status"] != "published":
                now = self.clock.now().isoformat()
                self.db.execute(
                    """
                    UPDATE entity_platform_status
                    SET status='published', published_at=?, release_url=COALESCE(?, release_url)
                    WHERE entity_type=? AND entity_id=? AND platform=?
                    """,
                    (now, post.release_url, row["entity_type"], row["entity_id"], row["platform"]),
                )
                updated += 1
        return updated


class Reconciliation:
    def __init__(self, db: Database, postiz: PostizClient, clock: Clock):
        self.db = db
        self.postiz = postiz
        self.clock = clock

    def run(self) -> dict[str, int]:
        """Two-way reconciliation."""
        # 1. Our scheduled must exist in Postiz
        our = self.db.fetchall(
            """
            SELECT entity_type, entity_id, platform, postiz_post_id
            FROM entity_platform_status
            WHERE status IN ('scheduled', 'updating') AND postiz_post_id IS NOT NULL
            """
        )
        missing = 0
        for row in our:
            if not self.postiz.get_post(row["postiz_post_id"]):
                self.db.execute(
                    "UPDATE entity_platform_status SET status='error', last_error='reconciliation_missing' "
                    "WHERE entity_type=? AND entity_id=? AND platform=?",
                    (row["entity_type"], row["entity_id"], row["platform"]),
                )
                missing += 1

        # 2. Postiz scheduled not in our DB (черновики не считаем — они паркуются осознанно)
        postiz_posts = self.postiz.list_scheduled()
        known_ids = {r["postiz_post_id"] for r in our}
        orphans = 0
        for p in postiz_posts:
            if p.id not in known_ids:
                state = (getattr(p, "status", "") or "").lower()
                if state in ("draft", "drafts"):
                    continue
                orphans += 1
                self.db.log("system", None, p.platform, "orphan_detected", p.id)
                logger.warning("Orphan post in Postiz: %s (%s)", p.id, p.platform)

        return {"missing": missing, "orphans": orphans}
