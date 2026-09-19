from __future__ import annotations

import logging
from datetime import UTC, datetime

from .clock import Clock
from .config import AppConfig
from .db import Database
from .telegram_bot import TelegramNotifier

logger = logging.getLogger(__name__)


class TailManager:
    def __init__(self, db: Database, cfg: AppConfig, clock: Clock, tg: TelegramNotifier):
        self.db = db
        self.cfg = cfg
        self.clock = clock
        self.tg = tg

    def is_tail(self, platform: str) -> bool:
        row = self.db.fetchone(
            "SELECT series_tail_mode FROM platform_queue_state WHERE platform=?",
            (platform,),
        )
        return bool(row and row["series_tail_mode"])

    def on_new_long_video(self, platform: str, video_id: int) -> None:
        """New long video resets tail and pending question."""
        now = self.clock.now().isoformat()
        self.db.execute(
            """
            UPDATE platform_queue_state
            SET series_tail_mode=0,
                active_long_video_id=?,
                last_long_video_at=?,
                pending_series_end_question=0,
                pending_series_end_at=NULL,
                updated_at=?
            WHERE platform=?
            """,
            (video_id, now, now, platform),
        )
        logger.info("Tail reset on %s due to new long video %s", platform, video_id)

    def check_soft_enter(self, platform: str) -> None:
        """If no new long video for soft_enter_days → ask user."""
        row = self.db.fetchone(
            "SELECT last_long_video_at, series_tail_mode, pending_series_end_question, "
            "last_series_end_question_at FROM platform_queue_state WHERE platform=?",
            (platform,),
        )
        if not row or row["series_tail_mode"]:
            return
        last = row["last_long_video_at"]
        if not last:
            return
        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=UTC)
        days = (self.clock.now() - last_dt).days
        if days < self.cfg.tail.soft_enter_days:
            return
        # cooldown
        if row["last_series_end_question_at"]:
            prev = datetime.fromisoformat(row["last_series_end_question_at"])
            if prev.tzinfo is None:
                prev = prev.replace(tzinfo=UTC)
            if (self.clock.now() - prev).days < self.cfg.tail.series_end_question_cooldown_days:
                return
        now = self.clock.now().isoformat()
        self.db.execute(
            "UPDATE platform_queue_state SET pending_series_end_question=1, "
            "pending_series_end_at=?, last_series_end_question_at=?, updated_at=? WHERE platform=?",
            (now, now, now, platform),
        )
        self.tg.ask_series_end(platform)

    def should_pause_standalone(self, platform: str) -> bool:
        return self.is_tail(platform) and self.cfg.tail.pause_standalone_during_tail

    def use_all_short_slots(self, platform: str) -> bool:
        return self.is_tail(platform) and self.cfg.tail.use_all_short_slots

    def expire_pending_questions(self) -> int:
        """Clear pending series_end questions past TTL."""
        ttl = self.cfg.tail.series_end_question_ttl_days
        rows = self.db.fetchall(
            "SELECT platform, pending_series_end_at FROM platform_queue_state "
            "WHERE pending_series_end_question=1 AND pending_series_end_at IS NOT NULL"
        )
        n = 0
        now = self.clock.now()
        for r in rows:
            try:
                at = datetime.fromisoformat(r["pending_series_end_at"])
                if at.tzinfo is None:
                    at = at.replace(tzinfo=UTC)
            except Exception:
                continue
            if (now - at).days >= ttl:
                self.db.execute(
                    "UPDATE platform_queue_state SET pending_series_end_question=0, "
                    "pending_series_end_at=NULL, updated_at=? WHERE platform=?",
                    (now.isoformat(), r["platform"]),
                )
                n += 1
                logger.info("Expired series_end question on %s", r["platform"])
        return n

