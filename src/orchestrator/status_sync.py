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
            SELECT entity_type, entity_id, platform, postiz_post_id, status,
                   postiz_scheduled_for, release_url, last_error
            FROM entity_platform_status
            WHERE postiz_post_id IS NOT NULL AND postiz_post_id != ''
              AND (
                status IN ('scheduled', 'updating', 'error')
                OR (status='published' AND (release_url IS NULL OR release_url=''))
              )
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
                # R8: N consecutive misses → error (soft: first misses only warn)
                prev = row.get("last_error") or ""
                streak = 0
                if prev.startswith("missing_in_postiz:"):
                    try:
                        streak = int(prev.split(":")[1])
                    except Exception:
                        streak = 1
                streak += 1
                threshold = int(getattr(self.cfg, "postiz_missing_error_after", 3) or 3)
                if streak >= threshold:
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='error', "
                        "last_error=? WHERE entity_type=? AND entity_id=? AND platform=?",
                        (f"missing_in_postiz:{streak}",
                         row["entity_type"], row["entity_id"], row["platform"]),
                    )
                else:
                    self.db.execute(
                        "UPDATE entity_platform_status SET last_error=? "
                        "WHERE entity_type=? AND entity_id=? AND platform=?",
                        (f"missing_in_postiz:{streak}",
                         row["entity_type"], row["entity_id"], row["platform"]),
                    )
                    logger.warning(
                        "get_post miss %s/%s/%s streak=%s/%s",
                        row["entity_type"], row["entity_id"], row["platform"],
                        streak, threshold,
                    )
                updated += 1
                continue
            st = self._normalize_postiz_status(getattr(post, "status", None))
            if st == "error" and row["status"] != "error":
                self.db.execute(
                    "UPDATE entity_platform_status SET status='error', "
                    "last_error='postiz_error' WHERE entity_type=? AND entity_id=? "
                    "AND platform=?",
                    (row["entity_type"], row["entity_id"], row["platform"]),
                )
                updated += 1
                continue
            # L29: treat released/completed as published; persist release_url when present
            if st == "published" and row["status"] != "published":
                now = self.clock.now().isoformat()
                self.db.execute(
                    """
                    UPDATE entity_platform_status
                    SET status='published', published_at=?, release_url=COALESCE(?, release_url),
                        last_error=NULL
                    WHERE entity_type=? AND entity_id=? AND platform=?
                    """,
                    (now, post.release_url, row["entity_type"], row["entity_id"], row["platform"]),
                )
                updated += 1
            elif st == "published" and post.release_url and not row.get("release_url"):
                # already published locally but URL just appeared
                self.db.execute(
                    "UPDATE entity_platform_status SET release_url=? "
                    "WHERE entity_type=? AND entity_id=? AND platform=? "
                    "AND (release_url IS NULL OR release_url='')",
                    (post.release_url, row["entity_type"], row["entity_id"], row["platform"]),
                )
                updated += 1
            else:
                # P1-4: пост найден — снимаем ложную ошибку «пропал в Postiz» и возвращаем
                # строку из error в рабочее состояние. Раньше счётчик не сбрасывался (порог
                # суммировал промахи за всю историю), а status='error' был терминальным.
                prev_err = row.get("last_error") or ""
                if prev_err.startswith("missing_in_postiz:") or (
                    row["status"] == "error" and prev_err == "reconciliation_missing"
                ):
                    new_status = row["status"]
                    if new_status == "error":
                        new_status = st if st in ("scheduled", "updating") else "scheduled"
                    self.db.execute(
                        "UPDATE entity_platform_status SET status=?, last_error=NULL "
                        "WHERE entity_type=? AND entity_id=? AND platform=?",
                        (new_status, row["entity_type"], row["entity_id"], row["platform"]),
                    )
                    updated += 1
                    logger.info(
                        "Recovered %s/%s/%s from %s -> %s",
                        row["entity_type"], row["entity_id"], row["platform"],
                        prev_err, new_status,
                    )
        return updated

    @staticmethod
    def _normalize_postiz_status(raw: str | None) -> str:
        """Map Postiz state strings to local statuses (L29)."""
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
        return s


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
        # published-строки тоже считаются «нашими» (иначе ложные orphans)
        for r in self.db.fetchall(
                "SELECT postiz_post_id FROM entity_platform_status "
                "WHERE postiz_post_id IS NOT NULL AND postiz_post_id != ''"):
            known_ids.add(r["postiz_post_id"])
        # P0.8: активные тест-посты — не сироты (отдельный контур test_publish)
        _sched: set[str] = set()
        for r in self.db.fetchall(
                "SELECT details FROM publish_log WHERE action='test_scheduled'"):
            pid = (r["details"] or "").strip().split(" ", 1)[0]
            if pid:
                _sched.add(pid)
        for r in self.db.fetchall(
                "SELECT details FROM publish_log WHERE action='test_cancelled'"):
            pid = (r["details"] or "").strip()
            _sched.discard(pid)
        known_ids |= _sched
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
