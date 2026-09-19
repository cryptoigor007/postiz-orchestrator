from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from . import sched_settings
from .clock import Clock
from .config import AppConfig
from .db import Database
from .publisher import Publisher
from .safety import SafetyChecker
from .slots import next_long_video_dates, thematic_slot_days

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

    def _pick_path(self, row, platform: str, pcfg=None):
        """Путь под платформу (platform_paths) или общий wide/vertical/video."""
        try:
            pm = json.loads(row.get("platform_paths") or "{}")
            if platform in pm and pm[platform]:
                return pm[platform]
        except Exception:
            pass
        if pcfg is not None:
            return row["wide_path"] if pcfg.video_variant == "wide" else row["vertical_path"]
        return row.get("video_path")

    def _safe_publish(self, *args, **kwargs):
        """Публикация с изоляцией: сбой одного поста не ломает весь цикл."""
        try:
            return self.publisher.publish(*args, **kwargs)
        except Exception as e:
            logger.exception("publish failed (%s / %s)",
                             args[0] if args else "", args[1] if len(args) > 1 else "")
            platform = args[2] if len(args) > 2 else ""
            if platform and hasattr(self, "safety") and self.safety is not None:
                try:
                    self.safety.handle_error(str(platform), str(e))
                except Exception:
                    logger.exception("safety.handle_error failed")
            return None

    def _backlog_active(self, platform: str) -> bool:
        """True, если для платформы идёт распределение неопубликованного остатка."""
        row = self.db.fetchone(
            "SELECT series_tail_mode FROM platform_queue_state WHERE platform=?",
            (platform,))
        if not row or not row["series_tail_mode"]:
            return False
        cnt = self.db.fetchone(
            """
            SELECT COUNT(*) AS c FROM shorts s
            WHERE s.parent_video_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM entity_platform_status eps
                  WHERE eps.entity_type='short' AND eps.entity_id=s.id
                    AND eps.platform=? AND eps.status IN ('scheduled','published','skipped'))
            """,
            (platform,))
        return bool(cnt and (cnt["c"] or 0) > 0)

    def _start_ref(self, start_date: str | None):
        """UTC-момент «за минуту до начала даты» для генерации слотов с указанной даты."""
        if not start_date:
            return None
        try:
            from datetime import timedelta

            from .slots import get_tz
            y, m, d = (int(x) for x in str(start_date).split("-"))
            tz = get_tz(self.cfg.timezone)
            dt = datetime(y, m, d, tzinfo=tz) - timedelta(minutes=1)
            return dt.astimezone(UTC)
        except Exception:
            return None

    def schedule_long_videos(self, start_date: str | None = None) -> int:
        """Place ready long videos into future slots (per platform, effective settings)."""
        now = self.clock.now()
        ref = self._start_ref(start_date) or now
        videos = self.db.fetchall(
            "SELECT id, wide_path, vertical_path, platform_paths, title_text, description_text, hashtags_text "
            "FROM long_videos ORDER BY created_at"
        )
        count = 0
        for platform, pcfg in self.cfg.platforms.items():
            if not pcfg.enabled:
                continue
            if getattr(pcfg, "post_mode", "media") == "link":
                continue  # только ссылки: видео на этой платформе не ставим
            if self._backlog_active(platform):
                continue  # сначала выкладываем остаток предыдущей серии
            eff = sched_settings.effective(self.db, self.cfg, platform, "long")
            future_slots = next_long_video_dates(
                eff.get("days") or ["tue", "fri"],
                eff.get("time") or "16:00",
                ref, count=20,
                exception_days=eff.get("exception_days", []),
                tz_name=self.cfg.timezone,
            )
            if not future_slots:
                continue
            limit = sched_settings.effective_daily_limit(self.db, self.cfg, platform)
            for video in videos:
                exists = self.db.fetchone(
                    "SELECT 1 FROM entity_platform_status WHERE entity_type='long_video' "
                    "AND entity_id=? AND platform=? "
                    "AND status IN ('scheduled','published','skipped')",
                    (video["id"], platform))
                if exists:
                    continue
                path = self._pick_path(video, platform, pcfg)
                if not path:
                    continue
                for slot in future_slots:
                    ok, _ = self.safety.can_schedule(platform, slot, limit)
                    if ok:
                        content = {
                            "title": video["title_text"] or "",
                            "description": video["description_text"] or "",
                            "hashtags": video["hashtags_text"] or "",
                        }
                        post = self._safe_publish(
                            "long_video", video["id"], platform, path, content, slot)
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
            # опубликовано (в т.ч. без ссылки) или ещё запланировано — ставим с плейсхолдером
            parent = self.db.fetchone(
                "SELECT * FROM entity_platform_status WHERE entity_type='long_video' "
                "AND entity_id=? AND platform=? AND status IN ('published','scheduled')",
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
            long_dt = long_dt.replace(tzinfo=UTC)

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
                next_dt = next_dt.replace(tzinfo=UTC)

        eff = sched_settings.effective(self.db, self.cfg, platform, "thematic")
        default_time = eff.get("time") or "20:30"
        slots = thematic_slot_days(long_dt, next_dt, default_time, tz_name=self.cfg.timezone)
        floor_raw = sched_settings.shorts_start_date(self.db)
        if floor_raw and slots:
            try:
                from datetime import date as _date

                from .slots import get_tz
                y, m, d = (int(x) for x in floor_raw.split("-"))
                floor = _date(y, m, d)
                tz = get_tz(self.cfg.timezone)
                slots = [sl for sl in slots if sl.astimezone(tz).date() >= floor]
            except Exception:
                logger.warning("bad shorts_start_date: %s", floor_raw)
        if not slots:
            return 0

        short_ids = [s["id"] for s in shorts]
        # один шорт на день-слот (ровно в 20:30); остаток уходит в «Остаток»
        assignments = list(zip(short_ids, slots, strict=False))

        pcfg = self.cfg.platforms[platform]
        if getattr(pcfg, "post_mode", "media") == "link":
            return 0
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
            path = self._pick_path(short, platform) or short["video_path"]
            if not path:
                continue
            # adjust slot if needed for safety
            final_slot = self.safety.find_next_slot(platform, sched, pcfg.daily_limit)
            if not final_slot:
                continue
            post = self._safe_publish(
                "short", sid, platform, path, content, final_slot
            )
            if post:
                count += 1
        return count



    def schedule_backlog(self, platform: str, start_date: str | None = None) -> int:
        """Публикует остаток (неопубликованные шортсы серий) по свободным слотам."""
        pcfg = self.cfg.platforms.get(platform)
        if not pcfg or not pcfg.enabled:
            return 0
        shorts = self.db.fetchall(
            """
            SELECT s.id, s.video_path, s.platform_paths, s.title_text, s.description_text, s.hashtags_text
            FROM shorts s
            WHERE s.parent_video_id IS NOT NULL AND s.video_path IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM entity_platform_status eps
                  WHERE eps.entity_type='short' AND eps.entity_id=s.id
                    AND eps.platform=? AND eps.status IN ('scheduled','published','skipped'))
            ORDER BY s.parent_video_id, s.order_index, s.id
            """,
            (platform,),
        )
        if not shorts:
            return 0
        slots = self._backlog_slots(start_date=start_date)
        count = 0
        for s in shorts:
            for slot in slots:
                ok, _ = self.safety.can_schedule(platform, slot, pcfg.daily_limit)
                if not ok:
                    continue
                content = {
                    "title": s["title_text"] or "",
                    "description": s["description_text"] or "",
                    "hashtags": s["hashtags_text"] or "",
                }
                post = self._safe_publish(
                    "short", s["id"], platform,
                    self._pick_path(s, platform) or s["video_path"], content, slot
                )
                if post:
                    count += 1
                    break
        return count

    def schedule_telegram_links(self) -> int:
        """Telegram (post_mode=link): текстовый пост со ссылкой на YouTube после публикации видео."""
        tcfg = self.cfg.platforms.get("telegram")
        if not tcfg or not tcfg.enabled or getattr(tcfg, "post_mode", "media") != "link":
            return 0
        delay = int(getattr(self.cfg, "telegram_link_delay_min", 15) or 0)
        limit = sched_settings.effective_daily_limit(self.db, self.cfg, "telegram")
        count = 0
        for etype, table in (("long_video", "long_videos"), ("short", "shorts")):
            rows = self.db.fetchall(
                """
                SELECT eps.entity_id AS id, eps.release_url AS url
                FROM entity_platform_status eps
                WHERE eps.entity_type=? AND eps.platform='youtube'
                  AND eps.status='published' AND eps.release_url IS NOT NULL
                """,
                (etype,),
            )
            for r in rows:
                exists = self.db.fetchone(
                    "SELECT 1 FROM entity_platform_status "
                    "WHERE entity_type=? AND entity_id=? AND platform='telegram'",
                    (etype, r["id"]),
                )
                if exists:
                    continue
                item = self.db.fetchone(
                    f"SELECT title_text, description_text, hashtags_text FROM {table} WHERE id=?",
                    (r["id"],),
                )
                if not item:
                    continue
                tmpl = self.cfg.description_templates.get(
                    "telegram_link", "{title}\n\n{description}\n\n▶ Смотреть: {link}"
                )
                text = tmpl.format(
                    title=item["title_text"] or "",
                    description=item["description_text"] or "",
                    link=r["url"] or "",
                ).strip()
                when = self.clock.now() + timedelta(minutes=delay)
                ok, reason = self.safety.can_schedule("telegram", when, limit)
                if not ok:
                    logger.info("telegram link skip (%s/%s): %s", etype, r["id"], reason)
                    continue
                content = {
                    "title": item["title_text"] or "",
                    "description": text,
                    "hashtags": item["hashtags_text"] or "",
                }
                post = self._safe_publish(etype, r["id"], "telegram", None, content, when)
                if post:
                    count += 1
        return count

    def _backlog_slots(self, days: int = 30, start_date: str | None = None) -> list[datetime]:
        """Свободные слоты: слот серии + обычные шортсы + тематические."""
        from datetime import timedelta

        from .slots import DAY_MAP, get_tz, local_to_utc, parse_time

        tz = get_tz(self.cfg.timezone)
        long_sched = self.cfg.schedules.get("long_video", {})
        long_days = {DAY_MAP[d.lower()[:3]] for d in long_sched.get("days", ["tue", "fri"])
                     if d.lower()[:3] in DAY_MAP}
        long_time = long_sched.get("time", "16:00")
        sa = self.cfg.schedules.get("shorts_standalone", {})
        sa_days = {DAY_MAP[d.lower()[:3]] for d in sa.get("days", []) if d.lower()[:3] in DAY_MAP}
        sa_times = sa.get("times", [])
        th_time = self.cfg.schedules.get("shorts_thematic", {}).get("default_time", "20:30")

        now = self.clock.now()
        local_today = now.astimezone(tz).date()
        if start_date:
            try:
                from datetime import date as _date
                y, m, d = (int(x) for x in start_date.split("-"))
                local_today = _date(y, m, d)
            except Exception:
                pass
        out: list[datetime] = []
        for i in range(days):
            d = local_today + timedelta(days=i)
            times = [th_time]
            if d.weekday() in long_days:
                times.append(long_time)
            if d.weekday() in sa_days:
                times.extend(sa_times)
            for ts in times:
                dt = local_to_utc(d, parse_time(ts), self.cfg.timezone)
                if dt > now:
                    out.append(dt)
        return sorted(set(out))

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
                long_dt = long_dt.replace(tzinfo=UTC)
            next_dt = None
            if i + 1 < len(rows):
                nraw = rows[i + 1]["postiz_scheduled_for"] or rows[i + 1]["published_at"]
                if nraw:
                    next_dt = datetime.fromisoformat(nraw)
                    if next_dt.tzinfo is None:
                        next_dt = next_dt.replace(tzinfo=UTC)
            occupied |= thematic_days_set(long_dt, next_dt, self.cfg.timezone)
        return occupied

    def schedule_standalone_shorts(self, tail_manager=None, start_date: str | None = None) -> int:
        """Schedule ShortsMaker standalone shorts on free (non-thematic) days."""
        from datetime import timedelta

        from .slots import DAY_MAP, get_tz, local_to_utc, parse_time

        now = self.clock.now()
        tz = get_tz(self.cfg.timezone)
        local_today = now.astimezone(tz).date()
        if start_date:
            try:
                from datetime import date as _date
                y, m, d = (int(x) for x in str(start_date).split("-"))
                local_today = _date(y, m, d)
            except Exception:
                pass

        ready = self.db.fetchall(
            """
            SELECT s.id, s.video_path, s.platform_paths, s.title_text, s.description_text, s.hashtags_text
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

        count = 0
        for platform, pcfg in self.cfg.platforms.items():
            if not pcfg.enabled:
                continue
            if getattr(pcfg, "post_mode", "media") == "link":
                continue
            if tail_manager and tail_manager.should_pause_standalone(platform):
                continue
            eff = sched_settings.effective(self.db, self.cfg, platform, "standalone")
            days = eff.get("days") or ["mon", "wed", "thu", "sat", "sun"]
            times = eff.get("times") or ["12:00", "18:00"]
            limit = sched_settings.effective_daily_limit(self.db, self.cfg, platform)
            exceptions = set(eff.get("exception_days") or [])
            weekday_set = {DAY_MAP[d.lower()[:3]] for d in days}
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
                            ok, _ = self.safety.can_schedule(platform, candidate, limit)
                            if ok:
                                content = {
                                    "title": short["title_text"] or "",
                                    "description": short["description_text"] or "",
                                    "hashtags": short["hashtags_text"] or "",
                                }
                                post = self._safe_publish(
                                    "short", short["id"], platform,
                                    self._pick_path(short, platform) or short["video_path"],
                                    content, candidate,
                                )
                                if post:
                                    count += 1
                                    placed = True
                                break
                        if placed:
                            break
                    cur += timedelta(days=1)
        return count
