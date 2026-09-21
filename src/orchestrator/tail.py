from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

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

    def on_new_long_video(
        self,
        platform: str,
        video_id: int,
        at: str | None = None,
        *,
        reset_tail: bool | None = None,
    ) -> None:
        """Record new long video time (L17: entity time, not now).

        Tail reset policy (L20 / §2): reset series_tail_mode only when the long is
        already published or scheduled within soft_enter_days of now. Far-future
        scheduled longs update active/last timestamps but do not clear tail.
        """
        now = self.clock.now()
        now_s = now.isoformat()
        at_s = at or now_s
        # Decide whether to clear tail
        do_reset = reset_tail
        if do_reset is None:
            do_reset = True
            try:
                at_dt = datetime.fromisoformat(at_s)
                if at_dt.tzinfo is None:
                    at_dt = at_dt.replace(tzinfo=UTC)
                # far-future schedule beyond soft_enter window → keep tail
                horizon = timedelta(days=int(self.cfg.tail.soft_enter_days or 0))
                if at_dt > now + horizon:
                    do_reset = False
            except Exception:
                do_reset = True
        if do_reset:
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
                (video_id, at_s, now_s, platform),
            )
            logger.info("Tail reset on %s due to long video %s at %s", platform, video_id, at_s)
        else:
            self.db.execute(
                """
                UPDATE platform_queue_state
                SET active_long_video_id=?,
                    last_long_video_at=?,
                    updated_at=?
                WHERE platform=?
                """,
                (video_id, at_s, now_s, platform),
            )
            logger.info(
                "Long %s on %s recorded at %s (tail kept — schedule beyond soft_enter)",
                video_id, platform, at_s,
            )

    def sync_new_long(self, platform: str) -> bool:
        """Отмечает последний запланированный/вышедший фильм.

        Без этого `check_soft_enter` никогда не срабатывал (last_long_video_at пустой).
        Возвращает True, если состояние обновилось.
        """
        row = self.db.fetchone(
            "SELECT entity_id, COALESCE(published_at, postiz_scheduled_for) AS at "
            "FROM entity_platform_status "
            "WHERE entity_type='long_video' AND platform=? "
            "  AND status IN ('scheduled','published','updating') "
            "ORDER BY COALESCE(published_at, postiz_scheduled_for) DESC LIMIT 1",
            (platform,),
        )
        if not row or not row["at"]:
            return False
        cur = self.db.fetchone(
            "SELECT active_long_video_id, last_long_video_at FROM platform_queue_state "
            "WHERE platform=?", (platform,))
        if cur and cur["active_long_video_id"] == row["entity_id"] and cur["last_long_video_at"]:
            return False
        # L17: pass entity scheduled/published time, not clock.now()
        self.on_new_long_video(platform, row["entity_id"], at=row["at"])
        return True

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
        """Clear pending series_end questions past TTL (L19).

        Respects tail.default_action: if distribute → enter series_tail_mode;
        otherwise just clear the pending flag (wait / manual).
        """
        ttl = self.cfg.tail.series_end_question_ttl_days
        rows = self.db.fetchall(
            "SELECT platform, pending_series_end_at FROM platform_queue_state "
            "WHERE pending_series_end_question=1 AND pending_series_end_at IS NOT NULL"
        )
        n = 0
        now = self.clock.now()
        action = (self.cfg.tail.default_action or "wait").lower()
        for r in rows:
            try:
                at = datetime.fromisoformat(r["pending_series_end_at"])
                if at.tzinfo is None:
                    at = at.replace(tzinfo=UTC)
            except Exception:
                continue
            if (now - at).days >= ttl:
                if action == "distribute":
                    self.db.execute(
                        "UPDATE platform_queue_state SET pending_series_end_question=0, "
                        "pending_series_end_at=NULL, series_tail_mode=1, "
                        "updated_at=? WHERE platform=?",
                        (now.isoformat(), r["platform"]),
                    )
                    logger.info(
                        "Expired series_end on %s → tail mode (default_action=distribute)",
                        r["platform"],
                    )
                else:
                    self.db.execute(
                        "UPDATE platform_queue_state SET pending_series_end_question=0, "
                        "pending_series_end_at=NULL, updated_at=? WHERE platform=?",
                        (now.isoformat(), r["platform"]),
                    )
                    logger.info(
                        "Expired series_end on %s → cleared (default_action=%s)",
                        r["platform"], action,
                    )
                n += 1
        return n

