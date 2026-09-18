from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import logging

from .clock import Clock
from .config import AppConfig
from .db import Database
from .publisher import Publisher
from .safety import SafetyChecker
from .slots import thematic_slot_days, distribute_shorts, next_long_video_dates

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        db: Database,
        cfg: AppConfig,
        publisher: Publisher,
        safety: SafetyChecker,
        clock: Clock,
    ):
        self.db = db
        self.cfg = cfg
        self.publisher = publisher
        self.safety = safety
        self.clock = clock

    def schedule_long_videos(self) -> int:
        """Place ready long videos into future slots."""
        sched = self.cfg.schedules.get("long_video", {})
        days = sched.get("days", ["tue", "fri"])
        time_str = sched.get("time", "16:00")
        exceptions = sched.get("exception_days", [])
        now = self.clock.now()

        future_slots = next_long_video_dates(days, time_str, now, count=20, exception_days=exceptions, tz_name=self.cfg.timezone)
        if not future_slots:
            return 0

        ready = self.db.fetchall(
            """
            SELECT lv.id, lv.wide_path, lv.vertical_path, lv.title_text, lv.description_text, lv.hashtags_text
            FROM long_videos lv
            WHERE NOT EXISTS (
                SELECT 1 FROM entity_platform_status eps
                WHERE eps.entity_type='long_video' AND eps.entity_id=lv.id
                  AND eps.status IN ('scheduled', 'published')
            )
            ORDER BY lv.created_at
            """
        )
        count = 0
        for video in ready:
            for platform, pcfg in self.cfg.platforms.items():
                if not pcfg.enabled:
                    continue
                path = video["wide_path"] if pcfg.video_variant == "wide" else video["vertical_path"]
                if not path:
                    continue
                # find free slot for this platform
                for slot in future_slots:
                    ok, _ = self.safety.can_schedule(platform, slot, pcfg.daily_limit)
                    if ok:
                        content = {
                            "title": video["title_text"] or "",
                            "description": video["description_text"] or "",
                            "hashtags": video["hashtags_text"] or "",
                        }
                        post = self.publisher.publish(
                            "long_video", video["id"], platform, path, content, slot
                        )
                        if post:
                            count += 1
                        break
        return count

    def schedule_thematic_shorts(self, parent_id: int, platform: str) -> int:
        """Schedule thematic shorts for a published long video that has release_url."""
        parent = self.db.fetchone(
            "SELECT * FROM entity_platform_status WHERE entity_type='long_video' "
            "AND entity_id=? AND platform=? AND status='published' AND release_url IS NOT NULL",
            (parent_id, platform),
        )
        if not parent:
            # check default_action path
            parent = self.db.fetchone(
                "SELECT * FROM entity_platform_status WHERE entity_type='long_video' "
                "AND entity_id=? AND platform=? AND status='published'",
                (parent_id, platform),
            )
            if not parent:
                return 0

        release_url = parent.get("release_url")
        template_key = "thematic_short" if release_url else "thematic_short_no_link"
        template = self.cfg.description_templates.get(template_key, "{description}")

        shorts = self.db.fetchall(
            """
            SELECT s.* FROM shorts s
            WHERE s.parent_video_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM entity_platform_status eps
                  WHERE eps.entity_type='short' AND eps.entity_id=s.id
                    AND eps.platform=? AND eps.status IN ('scheduled','published','skipped')
              )
            ORDER BY s.order_index, s.id
            LIMIT ?
            """,
            (parent_id, platform, self.cfg.limits.max_shorts_per_long_video),
        )
        if not shorts:
            return 0

        # determine slot window
        long_sched = parent.get("postiz_scheduled_for") or parent.get("published_at")
        long_dt = datetime.fromisoformat(long_sched) if long_sched else self.clock.now()
        if long_dt.tzinfo is None:
            long_dt = long_dt.replace(tzinfo=timezone.utc)

        # next long for this platform
        next_long = self.db.fetchone(
            """
            SELECT postiz_scheduled_for FROM entity_platform_status
            WHERE entity_type='long_video' AND platform=? AND entity_id != ?
              AND status IN ('scheduled','published')
              AND postiz_scheduled_for > ?
            ORDER BY postiz_scheduled_for LIMIT 1
            """,
            (platform, parent_id, long_dt.isoformat()),
        )
        next_dt = None
        if next_long and next_long["postiz_scheduled_for"]:
            next_dt = datetime.fromisoformat(next_long["postiz_scheduled_for"])
            if next_dt.tzinfo is None:
                next_dt = next_dt.replace(tzinfo=timezone.utc)

        default_time = self.cfg.schedules.get("shorts_thematic", {}).get("default_time", "20:30")
        slots = thematic_slot_days(long_dt, next_dt, default_time, tz_name=self.cfg.timezone)
        if not slots:
            return 0

        short_ids = [s["id"] for s in shorts]
        assignments = distribute_shorts(
            short_ids, slots, self.cfg.safety.min_interval_minutes
        )

        pcfg = self.cfg.platforms[platform]
        count = 0
        for sid, sched in assignments:
            short = next(s for s in shorts if s["id"] == sid)
            desc = template.format(
                description=short["description_text"] or "",
                link=release_url or self.cfg.link_update.placeholder_text,
            )
            content = {
                "title": short["title_text"] or "",
                "description": desc,
                "hashtags": short["hashtags_text"] or "",
            }
            path = short["video_path"]
            if not path:
                continue
            # adjust slot if needed for safety
            final_slot = self.safety.find_next_slot(platform, sched, pcfg.daily_limit)
            if not final_slot:
                continue
            post = self.publisher.publish(
                "short", sid, platform, path, content, final_slot
            )
            if post:
                count += 1
        return count



    def _thematic_dates_for_platform(self, platform: str) -> set:
        """Local dates occupied by thematic slots for this platform."""
        from .slots import thematic_days_set
        rows = self.db.fetchall(
            """
            SELECT entity_id, postiz_scheduled_for, published_at FROM entity_platform_status
            WHERE entity_type='long_video' AND platform=?
              AND status IN ('scheduled','published')
            ORDER BY COALESCE(postiz_scheduled_for, published_at)
            """,
            (platform,),
        )
        occupied = set()
        for i, r in enumerate(rows):
            raw = r["postiz_scheduled_for"] or r["published_at"]
            if not raw:
                continue
            long_dt = datetime.fromisoformat(raw)
            if long_dt.tzinfo is None:
                long_dt = long_dt.replace(tzinfo=timezone.utc)
            next_dt = None
            if i + 1 < len(rows):
                nraw = rows[i + 1]["postiz_scheduled_for"] or rows[i + 1]["published_at"]
                if nraw:
                    next_dt = datetime.fromisoformat(nraw)
                    if next_dt.tzinfo is None:
                        next_dt = next_dt.replace(tzinfo=timezone.utc)
            occupied |= thematic_days_set(long_dt, next_dt, self.cfg.timezone)
        return occupied

    def schedule_standalone_shorts(self, tail_manager=None) -> int:
        """Schedule ShortsMaker standalone shorts on free (non-thematic) days."""
        from .slots import DAY_MAP, parse_time, local_to_utc, get_tz
        from datetime import timedelta

        sched = self.cfg.schedules.get("shorts_standalone", {})
        days = sched.get("days", ["mon", "wed", "thu", "sat", "sun"])
        times = sched.get("times", ["12:00", "18:00"])
        exceptions = set(sched.get("exception_days", []))
        now = self.clock.now()
        tz = get_tz(self.cfg.timezone)
        local_today = now.astimezone(tz).date()

        ready = self.db.fetchall(
            """
            SELECT s.id, s.video_path, s.title_text, s.description_text, s.hashtags_text
            FROM shorts s
            WHERE s.source = 'shortsmaker'
              AND s.parent_video_id IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM entity_platform_status eps
                  WHERE eps.entity_type='short' AND eps.entity_id=s.id
                    AND eps.status IN ('scheduled','published','skipped')
              )
            ORDER BY s.created_at
            LIMIT ?
            """,
            (self.cfg.limits.max_posts_per_distribute,),
        )
        if not ready:
            return 0

        weekday_set = {DAY_MAP[d.lower()[:3]] for d in days}
        count = 0
        for platform, pcfg in self.cfg.platforms.items():
            if not pcfg.enabled:
                continue
            if tail_manager and tail_manager.should_pause_standalone(platform):
                continue
            thematic = self._thematic_dates_for_platform(platform)
            for short in ready:
                cur = local_today
                placed = False
                for _ in range(28):
                    if (
                        cur.weekday() in weekday_set
                        and cur.isoformat() not in exceptions
                        and cur not in thematic
                    ):
                        for ts in times:
                            t = parse_time(ts)
                            candidate = local_to_utc(cur, t, self.cfg.timezone)
                            if candidate <= now:
                                continue
                            ok, _ = self.safety.can_schedule(platform, candidate, pcfg.daily_limit)
                            if ok:
                                content = {
                                    "title": short["title_text"] or "",
                                    "description": short["description_text"] or "",
                                    "hashtags": short["hashtags_text"] or "",
                                }
                                post = self.publisher.publish(
                                    "short", short["id"], platform,
                                    short["video_path"], content, candidate,
                                )
                                if post:
                                    count += 1
                                    placed = True
                                break
                        if placed:
                            break
                    cur += timedelta(days=1)
        return count
