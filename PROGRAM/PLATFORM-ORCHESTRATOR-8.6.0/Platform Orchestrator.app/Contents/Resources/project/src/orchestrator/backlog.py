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

    def _account_id(self, platform: str, account_id: str = "") -> str:
        aid = str(account_id or "").strip()
        if aid:
            return aid
        rows = self.db.fetchall(
            "SELECT DISTINCT account_id FROM entity_platform_status "
            "WHERE platform=? AND account_id IS NOT NULL AND account_id!=''",
            (platform,),
        )
        accounts = sorted({str(r.get("account_id") or "").strip() for r in rows or [] if str(r.get("account_id") or "").strip()})
        if len(accounts) > 1:
            raise ValueError(f"account_scope_required:{platform}")
        if len(accounts) == 1:
            return accounts[0]
        # Preserve the legacy platform-wide state when there is no observed account scope.
        # Callers that operate an explicitly configured account pass account_id directly.
        return ""

    def unposted_series_shorts(self, platform: str, account_id: str = "") -> list[dict]:
        pcfg = self.cfg.platforms.get(platform)
        if pcfg is not None and getattr(pcfg, "post_mode", "media") == "link":
            # link-платформа (Telegram) публикует ссылку после YouTube: своих слотов
            # и своего «остатка» у неё нет — иначе в «Остатке шортсов серии» висят
            # строки, которые встанут сами (ждём премьеру).
            return []
        rows = self.db.fetchall(
            """
            SELECT s.id, s.parent_video_id, s.order_index, s.video_path, s.platform_paths,
                   s.title_text, s.description_text, s.hashtags_text
            FROM shorts s
            WHERE s.parent_video_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM entity_platform_status eps
                  WHERE eps.entity_type='short' AND eps.entity_id=s.id
                    AND eps.platform=? AND (?='' OR eps.account_id=?)
                  AND eps.status IN ('scheduled','published','skipped'))
            ORDER BY s.parent_video_id, s.order_index, s.id
            """,
            (platform, self._account_id(platform, account_id), self._account_id(platform, account_id)),
        )
        sched = getattr(self, "scheduler", None)
        if sched is None:
            return rows
        # шортс из пакета другой платформы остатком этой платформы не считается
        return [r for r in rows if sched._pick_short_path(r, platform)]

    def has_backlog(self, platform: str, account_id: str = "") -> int:
        return len(self.unposted_series_shorts(platform, account_id))

    def _state(self, platform: str, account_id: str = "") -> dict | None:
        aid = self._account_id(platform, account_id)
        if aid:
            return self.db.fetchone(
                "SELECT pending_backlog_question, pending_backlog_at, series_tail_mode, last_series_end_question_at "
                "FROM platform_queue_account_state WHERE platform=? AND account_id=?", (platform, aid))
        return self.db.fetchone(
            "SELECT pending_backlog_question, pending_backlog_at, series_tail_mode, last_series_end_question_at "
            "FROM platform_queue_state WHERE platform=?", (platform,))

    def _set_state(self, platform: str, account_id: str, sql_fields: str, params: tuple) -> None:
        aid = self._account_id(platform, account_id)
        if aid:
            self.db.execute(
                f"INSERT INTO platform_queue_account_state(platform,account_id,{sql_fields}) VALUES(?, ?, " + ",".join("?" for _ in params) + ") "
                f"ON CONFLICT(platform,account_id) DO UPDATE SET " + ",".join(f"{x}=excluded.{x}" for x in [x.strip() for x in sql_fields.split(',')]),
                (platform, aid, *params),
            )
        else:
            self.db.execute(
                f"UPDATE platform_queue_state SET {', '.join(f'{x.strip()}=?' for x in sql_fields.split(','))} WHERE platform=?", (*params, platform)
            )

    def _decision_slot(self, platform: str, slot: datetime | None, account_id: str = "") -> datetime | None:
        """P1-5: слот, к которому относится решение (pending_backlog_at → last/next)."""
        if slot is not None:
            return slot
        st = self._state(platform, account_id)
        raw = (st or {}).get("pending_backlog_at")
        if raw:
            try:
                dt = datetime.fromisoformat(str(raw))
                return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            except Exception:
                logger.warning("invalid pending_backlog_at for %s", platform, exc_info=True)
        return self.last_long_slot(platform) or self.next_long_slot(platform)

    def awaiting(self, platform: str, account_id: str = "") -> bool:
        st = self._state(platform, account_id)
        return bool(st and st["pending_backlog_question"])

    # ---------- timing ----------

    def next_long_slot(self, platform: str, now: datetime | None = None) -> datetime | None:
        """P0.10: слот из effective-настроек платформы (override/группы/исключения)."""
        from . import sched_settings
        eff = sched_settings.effective(self.db, self.cfg, platform, "long")
        days = eff.get("days") or ["tue", "fri"]
        t = eff.get("time") or "16:00"
        slots = next_long_video_dates(days, t, now or self.clock.now(), count=1,
                                      exception_days=eff.get("exception_days", []),
                                      tz_name=self.cfg.timezone)
        return slots[0] if slots else None

    def needs_question(self, platform: str, now: datetime | None = None, account_id: str = "") -> datetime | None:
        now = now or self.clock.now()
        slot = self.next_long_slot(platform, now)
        if not slot:
            return None
        ask_at = slot - timedelta(minutes=self.cfg.tail.ask_minutes_before)
        if not (ask_at <= now < slot):
            return None
        if self.has_backlog(platform, account_id) == 0:
            return None
        # P1-5: если по этому слоту решение уже принято (wait/skip/distribute) — не спрашиваем снова
        if self.db.get_setting(f"backlog_slot_done_{platform}__{self._account_id(platform, account_id)}") == slot.isoformat():
            return None
        st = self._state(platform, account_id)
        if st and st["pending_backlog_question"] and \
                st["pending_backlog_at"] == slot.isoformat():
            return None
        return slot

    def ask(self, platform: str, slot: datetime, account_id: str = "") -> None:
        now = self.clock.now().isoformat()
        aid = self._account_id(platform, account_id)
        if aid:
            self.db.execute("INSERT INTO platform_queue_account_state(platform,account_id,pending_backlog_question,pending_backlog_at,last_series_end_question_at,updated_at) VALUES(?,?,1,?,?,?) ON CONFLICT(platform,account_id) DO UPDATE SET pending_backlog_question=1,pending_backlog_at=excluded.pending_backlog_at,last_series_end_question_at=excluded.last_series_end_question_at,updated_at=excluded.updated_at", (platform,aid,slot.isoformat(),now,now))
        else:
            self.db.execute("UPDATE platform_queue_state SET pending_backlog_question=1,pending_backlog_at=?,last_series_end_question_at=?,updated_at=? WHERE platform=?", (slot.isoformat(),now,now,platform))
        if self.notifier is not None:
            try:
                self.notifier.ask_backlog(
                    platform,
                    self.has_backlog(platform, account_id),
                    account_id=aid,
                )
            except Exception:
                logger.exception("notifier.ask_backlog failed")

    def resolve(self, platform: str, answer: str, slot: datetime | None = None, account_id: str = "") -> int:
        now = self.clock.now().isoformat()
        # P1-5: фиксируем решение по слоту — вопрос не повторяется, дефолт не переопределяет ответ
        dec_slot = self._decision_slot(platform, slot, account_id)
        if dec_slot is not None:
            self.db.set_setting(f"backlog_slot_done_{platform}__{self._account_id(platform, account_id)}", dec_slot.isoformat())
        if answer == "distribute":
            aid = self._account_id(platform, account_id)
            if aid:
                self.db.execute("INSERT INTO platform_queue_account_state(platform,account_id,pending_backlog_question,pending_backlog_at,series_tail_mode,updated_at) VALUES(?,?,0,NULL,1,?) ON CONFLICT(platform,account_id) DO UPDATE SET pending_backlog_question=0,pending_backlog_at=NULL,series_tail_mode=1,updated_at=excluded.updated_at", (platform,aid,now))
            else:
                self.db.execute("UPDATE platform_queue_state SET pending_backlog_question=0,pending_backlog_at=NULL,series_tail_mode=1,updated_at=? WHERE platform=?", (now,platform))
            n = 0
            if self.scheduler is not None:
                n = self.scheduler.schedule_backlog(platform, account_id=account_id)
            if self.has_backlog(platform, account_id) == 0:
                # остаток разложен — снимаем режим, можно запускать следующую серию
                aid = self._account_id(platform, account_id)
                if aid:
                    self.db.execute("UPDATE platform_queue_account_state SET series_tail_mode=0,updated_at=? WHERE platform=? AND account_id=?", (now,platform,aid))
                else:
                    self.db.execute("UPDATE platform_queue_state SET series_tail_mode=0,updated_at=? WHERE platform=?", (now,platform))
            self.db.log("system", None, platform, "backlog_distribute", str(n))
            if self.notifier is not None:
                try:
                    self.notifier.backlog_distributed(platform, n)
                except Exception:
                    logger.exception("notifier.backlog_distributed failed")
            return n
        # wait | skip
        aid = self._account_id(platform, account_id)
        if aid:
            self.db.execute("INSERT INTO platform_queue_account_state(platform,account_id,pending_backlog_question,pending_backlog_at,series_tail_mode,last_series_end_question_at,updated_at) VALUES(?,?,0,NULL,0,?,?) ON CONFLICT(platform,account_id) DO UPDATE SET pending_backlog_question=0,pending_backlog_at=NULL,series_tail_mode=0,last_series_end_question_at=excluded.last_series_end_question_at,updated_at=excluded.updated_at", (platform,aid,now,now))
        else:
            self.db.execute("UPDATE platform_queue_state SET pending_backlog_question=0,pending_backlog_at=NULL,series_tail_mode=0,last_series_end_question_at=?,updated_at=? WHERE platform=?", (now,now,platform))
        self.db.log("system", None, platform, f"backlog_{answer}", "")
        return 0

    def last_long_slot(self, platform: str, now: datetime | None = None) -> datetime | None:
        """Последний по времени слот серии (<= now) из effective-настроек платформы."""
        from . import sched_settings
        from .slots import DAY_MAP, get_tz, local_to_utc, parse_time
        now = now or self.clock.now()
        eff = sched_settings.effective(self.db, self.cfg, platform, "long")
        days = {DAY_MAP[d.lower()[:3]] for d in (eff.get("days") or ["tue", "fri"])
                if d.lower()[:3] in DAY_MAP}
        exceptions = set(eff.get("exception_days") or [])
        t = eff.get("time") or "16:00"
        tz = get_tz(self.cfg.timezone)
        local_today = now.astimezone(tz).date()
        for i in range(0, 15):
            d = local_today - timedelta(days=i)
            if d.weekday() in days and d.isoformat() not in exceptions:
                dt = local_to_utc(d, parse_time(t), self.cfg.timezone)
                if dt <= now:
                    return dt
        return None

    def missed_default(self, platform: str, now: datetime | None = None, account_id: str = "") -> int:
        """Окно вопроса пропущено (оркестратор был недоступен) -> применяем дефолт."""
        now = now or self.clock.now()
        if self.awaiting(platform, account_id):
            return 0
        slot = self.last_long_slot(platform, now)
        if not slot:
            return 0
        if self.db.get_setting(f"backlog_slot_done_{platform}__{self._account_id(platform, account_id)}") == slot.isoformat():
            return 0
        if self.has_backlog(platform, account_id) == 0:
            return 0
        if now - slot > timedelta(hours=24):
            return 0
        aid = self._account_id(platform, account_id)
        if self.cfg.tail.default_action != "distribute":
            self.db.set_setting(f"backlog_slot_done_{platform}__{aid}", slot.isoformat())
            return 0
        logger.info("Backlog missed-window default for %s[%s] at %s", platform, aid or "-", slot)
        self.db.set_setting(f"backlog_slot_done_{platform}__{aid}", slot.isoformat())
        return self.resolve(platform, "distribute", slot, account_id=account_id)

    def should_remind(self, platform: str, now: datetime | None = None, account_id: str = "") -> datetime | None:
        now = now or self.clock.now()
        st = self._state(platform, account_id)
        if not (st and st["pending_backlog_question"] and st["pending_backlog_at"]):
            return None
        raw = st["pending_backlog_at"]
        try:
            slot = datetime.fromisoformat(raw)
        except Exception:
            return None
        if slot.tzinfo is None:
            slot = slot.replace(tzinfo=UTC)
        if not (slot - timedelta(minutes=self.cfg.tail.reminder_minutes_before) <= now < slot):
            return None
        aid = self._account_id(platform, account_id)
        if self.db.get_setting(f"backlog_reminded_{platform}__{aid}") == raw:
            return None
        return slot

    def mark_reminded(self, platform: str, slot: datetime, account_id: str = "") -> None:
        aid = self._account_id(platform, account_id)
        self.db.set_setting(f"backlog_reminded_{platform}__{aid}", slot.isoformat())
        if self.notifier is not None:
            try:
                self.notifier.remind_backlog(platform, self.has_backlog(platform, account_id), account_id=aid)
            except Exception:
                logger.exception("notifier.remind_backlog failed")

    def auto_default(self, platform: str, now: datetime | None = None, account_id: str = "") -> int:
        now = now or self.clock.now()
        st = self._state(platform, account_id)
        if not (st and st["pending_backlog_question"] and st["pending_backlog_at"]):
            return 0
        try:
            slot = datetime.fromisoformat(st["pending_backlog_at"])
        except Exception:
            return 0
        if slot.tzinfo is None:
            slot = slot.replace(tzinfo=UTC)
        if now < slot:
            return 0
        action = self.cfg.tail.default_action
        answer = "distribute" if action == "distribute" else "wait"
        logger.info("Backlog default action for %s: %s", platform, answer)
        return self.resolve(platform, answer, slot, account_id=account_id)
