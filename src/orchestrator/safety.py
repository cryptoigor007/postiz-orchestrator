from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .clock import Clock
from .config import AppConfig, SafetyCfg
from .db import Database


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
        self.db.execute(
            "UPDATE platform_safety_state SET is_paused=1, paused_at=?, pause_reason=?, updated_at=? "
            "WHERE platform=?",
            (now, reason, now, platform),
        )
        self.db.log("system", None, platform, "pause", reason)

    def resume_platform(self, platform: str) -> None:
        now_dt = self.clock.now()
        now = now_dt.isoformat()
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

    def _count_posts_on_date(self, platform: str, target_date: str) -> int:
        """Count scheduled/published posts for platform on given date (YYYY-MM-DD)."""
        row = self.db.fetchone(
            """
            SELECT COUNT(*) AS cnt FROM entity_platform_status
            WHERE platform = ?
              AND status IN ('scheduled', 'updating', 'published')
              AND postiz_scheduled_for IS NOT NULL
              AND date(postiz_scheduled_for) = date(?)
            """,
            (platform, target_date),
        )
        return int(row["cnt"]) if row else 0

    def _get_last_scheduled(self, platform: str) -> datetime | None:
        row = self.db.fetchone(
            """
            SELECT postiz_scheduled_for FROM entity_platform_status
            WHERE platform = ? AND postiz_scheduled_for IS NOT NULL
              AND status IN ('scheduled', 'updating', 'published')
            ORDER BY postiz_scheduled_for DESC LIMIT 1
            """,
            (platform,),
        )
        return _parse_dt(row["postiz_scheduled_for"]) if row else None

    def can_schedule(self, platform: str, scheduled_for: datetime,
                     platform_daily_limit: int) -> tuple[bool, str]:
        """Check limits and min_interval for a proposed schedule time."""
        if self.is_platform_paused(platform):
            return False, "platform_paused"

        if scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=UTC)

        target_date = scheduled_for.date().isoformat()
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

        # min_interval
        last = self._get_last_scheduled(platform)
        if last:
            delta = (scheduled_for - last).total_seconds() / 60.0
            if delta < self.safety.min_interval_minutes:
                return False, f"min_interval ({delta:.1f} < {self.safety.min_interval_minutes})"

        return True, "ok"

    def find_next_slot(self, platform: str, base_time: datetime,
                       platform_daily_limit: int,
                       max_attempts: int = 48) -> datetime | None:
        """Find nearest time >= base_time that satisfies limits and min_interval."""
        candidate = base_time
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=UTC)
        interval = timedelta(minutes=self.safety.min_interval_minutes)

        for _ in range(max_attempts):
            ok, _ = self.can_schedule(platform, candidate, platform_daily_limit)
            if ok:
                return candidate
            candidate += interval
        return None

    def record_post(self, platform: str, scheduled_for: datetime) -> None:
        now = self.clock.now().isoformat()
        date_str = scheduled_for.date().isoformat()
        self.db.execute(
            """
            UPDATE platform_safety_state
            SET last_post_at = ?, posts_today = posts_today + 1,
                posts_today_date = ?, updated_at = ?
            WHERE platform = ?
            """,
            (scheduled_for.isoformat(), date_str, now, platform),
        )

    def start_warmup(self, platform: str) -> None:
        until = self.clock.now() + timedelta(days=self.safety.warmup_days)
        now = self.clock.now().isoformat()
        self.db.execute(
            "UPDATE platform_safety_state SET warmup_until=?, updated_at=? WHERE platform=?",
            (until.isoformat(), now, platform),
        )


    def handle_error(self, platform: str, error: str) -> None:
        """Classify and react to auth / serious errors."""
        now = self.clock.now().isoformat()
        self.db.execute(
            "UPDATE platform_safety_state SET last_error=?, last_error_at=?, updated_at=? WHERE platform=?",
            (error, now, now, platform),
        )
        err_l = error.lower()
        if any(a.lower() in err_l for a in self.safety.auth_errors):
            self.pause_platform(platform, f"auth: {error}")
            return
        if any(s.lower() in err_l for s in self.safety.serious_errors):
            action = self.safety.on_serious_error.get("action", "pause_platform")
            if action == "pause_platform":
                self.pause_platform(platform, f"serious: {error}")
            return
