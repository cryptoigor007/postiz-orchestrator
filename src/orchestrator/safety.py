from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from .clock import Clock
from .config import AppConfig, SafetyCfg
from .db import Database

logger = logging.getLogger(__name__)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


class SafetyChecker:
    def __init__(self, db: Database, cfg: AppConfig, clock: Clock):
        self.db = db
        self.cfg = cfg
        self.safety: SafetyCfg = cfg.safety
        self.clock = clock

    def is_platform_paused(self, platform: str) -> bool:
        row = self.db.fetchone(
            "SELECT is_paused, paused_at FROM platform_safety_state WHERE platform = ?",
            (platform,),
        )
        if not row or not row["is_paused"]:
            return False
        pause_hours = int(self.safety.on_serious_error.get("pause_hours") or 0)
        if pause_hours > 0 and row["paused_at"]:
            paused_at = _parse_dt(row["paused_at"])
            if paused_at and self.clock.now() >= paused_at + timedelta(hours=pause_hours):
                self.resume_platform(platform)
                return False
        return True

    def pause_platform(self, platform: str, reason: str) -> None:
        now = self.clock.now().isoformat()
        # P1.4: UPSERT — строка могла отсутствовать (свежая платформа/чистая БД)
        self.db.execute(
            "INSERT INTO platform_safety_state "
            "(platform, is_paused, paused_at, pause_reason, updated_at) "
            "VALUES (?, 1, ?, ?, ?) "
            "ON CONFLICT(platform) DO UPDATE SET is_paused=1, paused_at=excluded.paused_at, "
            "pause_reason=excluded.pause_reason, updated_at=excluded.updated_at",
            (platform, now, reason, now),
        )
        self.db.log("system", None, platform, "pause", reason)

    def resume_platform(self, platform: str) -> None:
        now_dt = self.clock.now()
        now = now_dt.isoformat()
        # P1.4: гарантируем наличие строки (иначе resume на свежей БД — no-op)
        self.db.execute(
            "INSERT INTO platform_safety_state (platform, is_paused, updated_at) "
            "VALUES (?, 0, ?) ON CONFLICT(platform) DO NOTHING",
            (platform, now),
        )
        # if paused long enough — restart warmup
        row = self.db.fetchone(
            "SELECT paused_at FROM platform_safety_state WHERE platform=?",
            (platform,),
        )
        restart_warmup = False
        if row and row["paused_at"]:
            paused_at = _parse_dt(row["paused_at"])
            hours = self.safety.warmup_after_pause_hours
            if paused_at and (now_dt - paused_at).total_seconds() >= hours * 3600:
                restart_warmup = True
        self.db.execute(
            "UPDATE platform_safety_state SET is_paused=0, paused_at=NULL, pause_reason=NULL, "
            "updated_at=? WHERE platform=?",
            (now, platform),
        )
        if restart_warmup:
            self.start_warmup(platform)
            self.db.log("system", None, platform, "resume_warmup", "")
        else:
            self.db.log("system", None, platform, "resume", "")

    def _local_day_bounds(self, scheduled_for: datetime) -> tuple[str, str, str]:
        """Calendar day in cfg.timezone → (local_date_iso, utc_start_iso, utc_end_iso)."""
        from .slots import get_tz
        if scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=UTC)
        tz = get_tz(self.cfg.timezone)
        local = scheduled_for.astimezone(tz)
        day = local.date()
        start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=tz).astimezone(UTC)
        end = start + timedelta(days=1)
        return day.isoformat(), start.isoformat(), end.isoformat()

    def _count_posts_on_date(self, platform: str, target_date: str) -> int:
        """Count posts on calendar day target_date (YYYY-MM-DD) in cfg.timezone."""
        from .slots import get_tz
        try:
            y, m, d = (int(x) for x in target_date.split("-"))
        except Exception:
            return 0
        tz = get_tz(self.cfg.timezone)
        start = datetime(y, m, d, 0, 0, 0, tzinfo=tz).astimezone(UTC)
        end = start + timedelta(days=1)
        row = self.db.fetchone(
            """
            SELECT COUNT(*) AS cnt FROM entity_platform_status
            WHERE platform = ?
              AND status IN ('scheduled', 'updating', 'published')
              AND postiz_scheduled_for IS NOT NULL
              AND postiz_scheduled_for >= ? AND postiz_scheduled_for < ?
            """,
            (platform, start.isoformat(), end.isoformat()),
        )
        return int(row["cnt"]) if row else 0

    def can_schedule(self, platform: str, scheduled_for: datetime,
                     platform_daily_limit: int) -> tuple[bool, str]:
        """Check limits and min_interval for a proposed schedule time."""
        if self.is_platform_paused(platform):
            return False, "platform_paused"

        # L30: exception_days from sched_settings (YYYY-MM-DD in cfg.timezone)
        try:
            from . import sched_settings as _ss
            from .slots import get_tz
            block = _ss.platform_block(self.db, platform)
            # merge group override if any
            groups = _ss.load_groups(self.db)
            g = _ss.group_for(platform, groups)
            if g:
                settings = _ss.load_schedule_settings(self.db)
                gblock = settings.get(f"group:{g['name']}") or {}
                if isinstance(gblock, dict):
                    block = {**block, **gblock}
            # also from effective() for long kind
            try:
                eff = _ss.effective(self.db, self.cfg, platform, "long")
                for d in eff.get("exception_days") or []:
                    block.setdefault("exception_days", [])
                    if d not in block["exception_days"]:
                        block["exception_days"] = list(block.get("exception_days") or []) + [d]
            except Exception:
                logger.debug("pause-state parse failed", exc_info=True)
            exc = {str(d) for d in (block or {}).get("exception_days") or []}
            if exc:
                day = scheduled_for.astimezone(get_tz(self.cfg.timezone)).strftime("%Y-%m-%d")
                if day in exc:
                    return False, "exception_day"
        except Exception:
            logger.warning("exception_days: не смог проверить исключённые дни, защита пропущена",
                           exc_info=True)

        # P12: нормализуем до расчёта дня, иначе naive-время считается в UTC, а не в tz панели
        if scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=UTC)

        target_date, _, _ = self._local_day_bounds(scheduled_for)
        count = self._count_posts_on_date(platform, target_date)

        # warmup check
        safety_row = self.db.fetchone(
            "SELECT warmup_until FROM platform_safety_state WHERE platform = ?",
            (platform,),
        )
        warmup_until = _parse_dt(safety_row["warmup_until"]) if safety_row else None
        now = self.clock.now()
        limit = platform_daily_limit
        if warmup_until and now < warmup_until:
            limit = min(limit, self.safety.warmup_daily_limit)

        if count >= limit:
            return False, f"daily_limit_reached ({count}/{limit})"

        # min_interval: рядом со слотом (в обе стороны) не должно быть других постов
        win = self.safety.min_interval_minutes
        lo = (scheduled_for - timedelta(minutes=win)).isoformat()
        hi = (scheduled_for + timedelta(minutes=win)).isoformat()
        near = self.db.fetchone(
            """
            SELECT postiz_scheduled_for FROM entity_platform_status
            WHERE platform = ? AND postiz_scheduled_for IS NOT NULL
              AND status IN ('scheduled', 'updating', 'published')
              AND postiz_scheduled_for > ? AND postiz_scheduled_for < ?
            LIMIT 1
            """,
            (platform, lo, hi),
        )
        if near:
            return False, f"min_interval_conflict ({near['postiz_scheduled_for']})"

        return True, "ok"

    def record_post(self, platform: str, scheduled_for: datetime) -> None:
        """Update last_post_at and posts_today (reset when calendar day changes in cfg.timezone)."""
        now = self.clock.now().isoformat()
        if scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=UTC)
        date_str, _, _ = self._local_day_bounds(scheduled_for)
        row = self.db.fetchone(
            "SELECT posts_today, posts_today_date FROM platform_safety_state WHERE platform=?",
            (platform,),
        )
        if row is None:
            self.db.execute(
                """
                INSERT INTO platform_safety_state
                    (platform, last_post_at, posts_today, posts_today_date, updated_at)
                VALUES (?, ?, 1, ?, ?)
                """,
                (platform, scheduled_for.isoformat(), date_str, now),
            )
            return
        prev_date = row["posts_today_date"]
        if prev_date != date_str:
            new_count = 1
        else:
            new_count = int(row["posts_today"] or 0) + 1
        self.db.execute(
            """
            UPDATE platform_safety_state
            SET last_post_at = ?, posts_today = ?, posts_today_date = ?, updated_at = ?
            WHERE platform = ?
            """,
            (scheduled_for.isoformat(), new_count, date_str, now, platform),
        )

    def start_warmup(self, platform: str) -> None:
        until = self.clock.now() + timedelta(days=self.safety.warmup_days)
        now = self.clock.now().isoformat()
        self.db.execute(
            "INSERT INTO platform_safety_state (platform, warmup_until, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(platform) DO UPDATE SET warmup_until=excluded.warmup_until, "
            "updated_at=excluded.updated_at",
            (platform, until.isoformat(), now),
        )


    def handle_error(self, platform: str, error: str) -> None:
        """Classify and react to auth / serious errors."""
        now = self.clock.now().isoformat()
        self.db.execute(
            "UPDATE platform_safety_state SET last_error=?, last_error_at=?, updated_at=? WHERE platform=?",
            (error, now, now, platform),
        )
        err_l = error.lower()
        if any(a.lower() in err_l for a in getattr(self.safety, "auth_errors", [])):
            self.pause_platform(platform, f"auth: {error}")
            return
        # троттлинг Postiz/платформы — не пауза, просто запись об ошибке (ретраи делают своё дело)
        if any(r.lower() in err_l for r in getattr(self.safety, "rate_limit_errors", [])):
            return
        if any(s.lower() in err_l for s in self.safety.serious_errors):
            action = self.safety.on_serious_error.get("action", "pause_platform")
            if action == "pause_platform":
                self.pause_platform(platform, f"serious: {error}")
            return
