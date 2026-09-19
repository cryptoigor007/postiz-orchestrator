from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from .clock import Clock
from .config import AppConfig
from .db import Database
from .slots import next_long_video_dates

logger = logging.getLogger(__name__)


class BacklogManager:
    """Unposted shorts of a finished series ("backlog").

    When a series' slot (e.g. Tue/Fri 16:00) approaches and no new episode is
    ready, ask the user (ask_minutes_before) with actions:
      - distribute: schedule the backlog now (default if no answer by slot time)
      - wait:       keep waiting for a new episode
      - skip:       do not publish the backlog for now
    """

    def __init__(self, db: Database, cfg: AppConfig, clock: Clock,
                 scheduler: Any = None, notifier: Any = None):
        self.db = db
        self.cfg = cfg
        self.clock = clock
        self.scheduler = scheduler
        self.notifier = notifier

    # ---------- state ----------

    def unposted_series_shorts(self, platform: str) -> list[dict]:
        return self.db.fetchall(
            """
            SELECT s.id, s.parent_video_id, s.order_index, s.video_path,
                   s.title_text, s.description_text, s.hashtags_text
            FROM shorts s
            WHERE s.parent_video_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM entity_platform_status eps
                  WHERE eps.entity_type='short' AND eps.entity_id=s.id
                    AND eps.platform=? AND eps.status IN ('scheduled','published','skipped'))
            ORDER BY s.parent_video_id, s.order_index, s.id
            """,
            (platform,),
        )

    def has_backlog(self, platform: str) -> int:
        return len(self.unposted_series_shorts(platform))

    def has_ready_long(self) -> bool:
        row = self.db.fetchone(
            """
            SELECT COUNT(*) AS c FROM long_videos lv
            WHERE NOT EXISTS (
                SELECT 1 FROM entity_platform_status eps
                WHERE eps.entity_type='long_video' AND eps.entity_id=lv.id
                  AND eps.status IN ('scheduled','published'))
            """
        )
        return bool(row and (row["c"] or 0) > 0)

    def _state(self, platform: str) -> dict | None:
        return self.db.fetchone(
            "SELECT pending_series_end_question, pending_series_end_at, series_tail_mode,"
            " last_series_end_question_at FROM platform_queue_state WHERE platform=?",
            (platform,),
        )

    def awaiting(self, platform: str) -> bool:
        st = self._state(platform)
        return bool(st and st["pending_series_end_question"])

    # ---------- timing ----------

    def next_long_slot(self, now: datetime | None = None) -> datetime | None:
        sched = self.cfg.schedules.get("long_video", {})
        days = sched.get("days", ["tue", "fri"])
        t = sched.get("time", "16:00")
        slots = next_long_video_dates(days, t, now or self.clock.now(),
                                      count=1, tz_name=self.cfg.timezone)
        return slots[0] if slots else None

    def needs_question(self, platform: str, now: datetime | None = None) -> datetime | None:
        now = now or self.clock.now()
        slot = self.next_long_slot(now)
        if not slot:
            return None
        ask_at = slot - timedelta(minutes=self.cfg.tail.ask_minutes_before)
        if not (ask_at <= now < slot):
            return None
        if self.has_backlog(platform) == 0:
            return None
        st = self._state(platform)
        if st and st["pending_series_end_question"] and \
                st["pending_series_end_at"] == slot.isoformat():
            return None
        return slot

    def reminder_due(self, platform: str, now: datetime | None = None) -> bool:
        now = now or self.clock.now()
        st = self._state(platform)
        if not (st and st["pending_series_end_question"] and st["pending_series_end_at"]):
            return False
        try:
            slot = datetime.fromisoformat(st["pending_series_end_at"])
        except Exception:
            return False
        if slot.tzinfo is None:
            slot = slot.replace(tzinfo=UTC)
        remind_at = slot - timedelta(minutes=self.cfg.tail.reminder_minutes_before)
        return remind_at <= now < slot

    # ---------- actions ----------

    def ask(self, platform: str, slot: datetime) -> None:
        now = self.clock.now().isoformat()
        self.db.execute(
            "UPDATE platform_queue_state SET pending_series_end_question=1, "
            "pending_series_end_at=?, last_series_end_question_at=?, updated_at=? WHERE platform=?",
            (slot.isoformat(), now, now, platform),
        )
        if self.notifier is not None:
            try:
                self.notifier.ask_backlog(platform, self.has_backlog(platform))
            except Exception:
                logger.exception("notifier.ask_backlog failed")

    def resolve(self, platform: str, answer: str, slot: datetime | None = None) -> int:
        now = self.clock.now().isoformat()
        if answer == "distribute":
            self.db.execute(
                "UPDATE platform_queue_state SET pending_series_end_question=0, "
                "pending_series_end_at=NULL, series_tail_mode=1, updated_at=? WHERE platform=?",
                (now, platform),
            )
            n = 0
            if self.scheduler is not None:
                n = self.scheduler.schedule_backlog(platform)
            if self.has_backlog(platform) == 0:
                # остаток разложен — снимаем режим, можно запускать следующую серию
                self.db.execute(
                    "UPDATE platform_queue_state SET series_tail_mode=0, updated_at=? WHERE platform=?",
                    (now, platform))
            self.db.log("system", None, platform, "backlog_distribute", str(n))
            if self.notifier is not None:
                try:
                    self.notifier.backlog_distributed(platform, n)
                except Exception:
                    logger.exception("notifier.backlog_distributed failed")
            return n
        # wait | skip
        self.db.execute(
            "UPDATE platform_queue_state SET pending_series_end_question=0, "
            "pending_series_end_at=NULL, series_tail_mode=0, last_series_end_question_at=?, "
            "updated_at=? WHERE platform=?",
            (now, now, platform),
        )
        self.db.log("system", None, platform, f"backlog_{answer}", "")
        return 0

    def should_remind(self, platform: str, now: datetime | None = None) -> datetime | None:
        now = now or self.clock.now()
        st = self._state(platform)
        if not (st and st["pending_series_end_question"] and st["pending_series_end_at"]):
            return None
        raw = st["pending_series_end_at"]
        try:
            slot = datetime.fromisoformat(raw)
        except Exception:
            return None
        if slot.tzinfo is None:
            slot = slot.replace(tzinfo=UTC)
        if not (slot - timedelta(minutes=self.cfg.tail.reminder_minutes_before) <= now < slot):
            return None
        if self.db.get_setting(f"backlog_reminded_{platform}") == raw:
            return None
        return slot

    def mark_reminded(self, platform: str, slot: datetime) -> None:
        self.db.set_setting(f"backlog_reminded_{platform}", slot.isoformat())
        if self.notifier is not None:
            try:
                self.notifier.remind_backlog(platform, self.has_backlog(platform))
            except Exception:
                logger.exception("notifier.remind_backlog failed")

    def auto_default(self, platform: str, now: datetime | None = None) -> int:
        now = now or self.clock.now()
        st = self._state(platform)
        if not (st and st["pending_series_end_question"] and st["pending_series_end_at"]):
            return 0
        try:
            slot = datetime.fromisoformat(st["pending_series_end_at"])
        except Exception:
            return 0
        if slot.tzinfo is None:
            slot = slot.replace(tzinfo=UTC)
        if now < slot:
            return 0
        action = self.cfg.tail.default_action
        answer = "distribute" if action == "distribute" else "wait"
        logger.info("Backlog default action for %s: %s", platform, answer)
        return self.resolve(platform, answer, slot)
