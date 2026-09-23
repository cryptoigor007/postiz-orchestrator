from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from . import sched_settings
from .clock import Clock
from .config import AppConfig
from .db import Database
from .publisher import Publisher
from .safety import SafetyChecker
from .slots import next_long_video_dates, thematic_slot_days

logger = logging.getLogger(__name__)

# P1-6: после ошибки create не дёргаем медиа повторно — кулдаун на пару (сущность, платформа)
PUBLISH_ERROR_COOLDOWN = timedelta(minutes=30)


class Scheduler:
    def __init__(
        self,
        db: Database,
        cfg: AppConfig,
        publisher: Publisher,
        safety: SafetyChecker,
        clock: Clock,
        telegram: Any = None,
    ):
        self.db = db
        self.cfg = cfg
        self.publisher = publisher
        self.safety = safety
        self.clock = clock
        self.telegram = telegram  # TelegramPublisher при platforms.telegram.send_via=bot
        self.job = None  # Job для прогресса/отмены (задаётся перед запуском)
        self._publish_cooldown: dict[str, datetime] = {}

    def _slot_for_safety(self, slot: datetime) -> datetime:
        """Same jitter as Publisher before can_schedule (L8)."""
        if not slot or not getattr(self.cfg.safety, "jitter_seconds", 0):
            return slot
        from .slots import apply_jitter
        jittered = apply_jitter(slot, self.cfg.safety.jitter_seconds)
        if jittered > self.clock.now():
            return jittered
        return slot


    def _cooldown_key(self, etype: str, eid: int, platform: str) -> str:
        return f"{etype}:{eid}:{platform}"

    def _in_publish_cooldown(self, etype: str, eid: int, platform: str) -> bool:
        until = self._publish_cooldown.get(self._cooldown_key(etype, eid, platform))
        return bool(until and self.clock.now() < until)

    def _mark_publish_failed(self, etype: str, eid: int, platform: str) -> None:
        self._publish_cooldown[self._cooldown_key(etype, eid, platform)] = \
            self.clock.now() + PUBLISH_ERROR_COOLDOWN

    @staticmethod
    def _platform_paths(row) -> dict[str, str]:
        try:
            pm = json.loads(row.get("platform_paths") or "{}")
        except Exception:
            logger.debug("scheduler parse failed", exc_info=True)
            return {}
        return pm if isinstance(pm, dict) else {}

    @staticmethod
    def _in_scope(folder_path: str | None, scope_roots: list | None) -> bool:
        """Попадает ли папка в «Папки для сканирования» (None/пусто — ограничения нет)."""
        if not scope_roots:
            return True
        fp = str(folder_path or "").split("::")[0]
        if not fp:
            return False
        for root in scope_roots:
            r = str(root).rstrip("/")
            if fp == r or fp.startswith(r + "/"):
                return True
        return False

    def _pick_path(self, row, platform: str, pcfg=None):
        """Путь под платформу.
        Если карта платформ заполнена (пакеты платформ видео мейкера) — она строгая:
        платформа без своего файла публикации не получает, подстановки другим форматом нет.
        Иначе — общий wide/vertical по формату платформы или video_path.
        """
        pm = self._platform_paths(row)
        if pm:
            return pm.get(platform)
        if pcfg is not None:
            wide = row.get("wide_path")
            vert = row.get("vertical_path")
            return wide if pcfg.video_variant == "wide" else vert
        return row.get("video_path")

    def _pick_short_path(self, short, platform: str):
        """Шортс под платформу: карта платформ строгая, иначе обычный файл шортса."""
        pm = self._platform_paths(short)
        if pm:
            return pm.get(platform)
        return self._pick_path(short, platform) or short.get("video_path")

    def _is_canonical(self, platform: str, when) -> bool:
        """Время поста обязано совпадать с одним из времён расписания платформы."""
        if when is None:
            return True
        times = sched_settings.all_times(self.db, self.cfg, platform)
        if not times:
            return True
        from .slots import get_tz, parse_time
        local = when.astimezone(get_tz(self.cfg.timezone))
        try:
            want = {parse_time(str(x)).strftime("%H:%M") for x in times}
        except Exception:
            logger.warning("расписание платформы %s: некорректное время %s", platform, times)
            want = {str(x) for x in times}
        return local.strftime("%H:%M") in want

    def _guard_busy(self, platform: str, slot: datetime | None) -> bool:
        """Слот занят постом в Postiz/n8n (анти-коллизии): пропускаем слот.

        Иначе каждый цикл планировщик бьётся в тот же занятый слот и пишет
        `safety_block: schedule_conflict` (наблюдали 1742 записи за 3 дня).
        """
        guard = getattr(self.publisher, "guard", None)
        if guard is None or slot is None:
            return False
        try:
            return bool(guard.conflict(platform, self._slot_for_safety(slot)))
        except Exception:
            logger.exception("guard.conflict failed (%s)", platform)
            return False

    def _safe_publish(self, *args, **kwargs):
        """Публикация с изоляцией: сбой одного поста не ломает весь цикл."""
        when = args[5] if len(args) > 5 else kwargs.get("scheduled_for")
        platform = str(args[2]) if len(args) > 2 else ""
        has_media = (args[3] is not None) if len(args) > 3 else True
        if when is not None and platform and has_media and not self._is_canonical(platform, when):
            logger.warning("Отклонено: время %s не из расписания (%s)", when, platform)
            try:
                self.db.log(args[0], args[1], platform, "non_canonical_slot", str(when))
            except Exception:
                pass
            return None
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

    def _entity_folder(self, etype: str, eid: int) -> str | None:
        """Папка сущности (фильма или шортса) — по ней определяется проект."""
        table = "long_videos" if etype == "long_video" else "shorts"
        row = self.db.fetchone(f"SELECT folder_path FROM {table} WHERE id=?", (eid,))
        return row["folder_path"] if row else None

    def _entity_project(self, etype: str, eid: int) -> str:
        """Проект сущности: у шортса сначала смотрим фильм-родителя, потом свою папку."""
        if etype == "long_video":
            return self.cfg.resolve_project(series_id=eid, folder=self._entity_folder(etype, eid))
        row = self.db.fetchone("SELECT folder_path, parent_video_id FROM shorts WHERE id=?", (eid,))
        if not row:
            return ""
        parent = row["parent_video_id"]
        if parent:
            prj = self.cfg.resolve_project(series_id=parent,
                                           folder=self._entity_folder("long_video", parent))
            if prj:
                return prj
        return self.cfg.project_of_folder(row["folder_path"])

    def _platform_ok(self, platform: str, *, etype: str | None = None, eid: int | None = None,
                     folder: str | None = None) -> bool:
        """Пускает ли платформа сущность: платформа без проекта — всё, проектная — своё."""
        pcfg = self.cfg.platforms.get(platform)
        if pcfg is None:
            return False
        if not (pcfg.project or ""):
            return True
        got = (self._entity_project(etype, eid) if (etype and eid is not None)
               else self.cfg.project_of_folder(folder))
        return got == pcfg.project

    def _backlog_active(self, platform: str) -> bool:
        """True, если для платформы идёт распределение неопубликованного остатка."""
        row = self.db.fetchone(
            "SELECT series_tail_mode FROM platform_queue_state WHERE platform=?",
            (platform,))
        if not row or not row["series_tail_mode"]:
            return False
        rows = self.db.fetchall(
            """
            SELECT s.id, s.video_path, s.platform_paths
            FROM shorts s
            WHERE s.parent_video_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM entity_platform_status eps
                  WHERE eps.entity_type='short' AND eps.entity_id=s.id
                    AND eps.platform=? AND eps.status IN ('scheduled','published','skipped'))
            """,
            (platform,))
        # шортс из пакета другой платформы не относится к «остатку» этой платформы
        return any(self._pick_short_path(r, platform) for r in rows)

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

    def schedule_long_videos(self, start_date: str | None = None,
                             scope_roots: list | None = None) -> int:
        """Place ready long videos into future slots (per platform, effective settings)."""
        now = self.clock.now()
        # start_date из прошлого не сужает окно: иначе все слоты в прошлом и план пуст
        ref = max(self._start_ref(start_date) or now, now)
        videos = self.db.fetchall(
            "SELECT id, folder_path, wide_path, vertical_path, platform_paths, title_text, "
            "description_text, hashtags_text, cover_path FROM long_videos ORDER BY created_at"
        )
        count = 0
        for platform, pcfg in self.cfg.platforms.items():
            if not pcfg.enabled:
                continue
            if getattr(pcfg, "post_mode", "media") == "link":
                continue  # только ссылки: видео на этой платформе не ставим
            if self._backlog_active(platform):
                continue  # сначала выкладываем остаток предыдущей серии
            # L21: pending series-end question blocks new long until resolved/expired
            pq = self.db.fetchone(
                "SELECT pending_series_end_question, "
                "COALESCE(pending_backlog_question,0) AS pending_backlog_question "
                "FROM platform_queue_state WHERE platform=?",
                (platform,),
            )
            if pq and (pq["pending_series_end_question"] or pq["pending_backlog_question"]):
                continue
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
            if self.job is not None:
                self.job.set_total(self.job.state.total + len(videos))
            for video in videos:
                if self.job is not None and self.job.cancelled:
                    break
                if not self._in_scope(video.get("folder_path"), scope_roots):
                    continue  # фильм вне «Папок для сканирования» не планируем
                if not self._platform_ok(platform, etype="long_video", eid=video["id"]):
                    continue  # фильм другого проекта в эту сеть не ставим
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
                if self._in_publish_cooldown("long_video", video["id"], platform):
                    continue
                for slot in future_slots:
                    # P1-7: слоты «в прошлом» (start_date из панели) Postiz публикует
                    # немедленно — для standalone такая защита уже была, для фильмов нет.
                    if slot <= now:
                        continue
                    if self._guard_busy(platform, slot):
                        continue  # слот занят постом в Postiz/n8n — берём следующий
                    ok, _ = self.safety.can_schedule(platform, self._slot_for_safety(slot), limit)
                    if ok:
                        content = {
                            "title": video["title_text"] or "",
                            "description": video["description_text"] or "",
                            "hashtags": video["hashtags_text"] or "",
                            "cover": video.get("cover_path") or "",
                        }
                        post = self._safe_publish(
                            "long_video", video["id"], platform, path, content, slot)
                        if post:
                            count += 1
                            if self.job is not None:
                                self.job.tick(1, f"Фильм #{video['id']} → {platform}")
                        else:
                            self._mark_publish_failed("long_video", video["id"], platform)
                        break
        return count

    def schedule_thematic_shorts(self, parent_id: int, platform: str,
                                 scope_roots: list | None = None) -> int:
        """Schedule thematic shorts for a published long video that has release_url."""
        _pcfg = self.cfg.platforms.get(platform)
        if _pcfg is not None and getattr(_pcfg, "post_mode", "media") == "link":
            # B: link-платформа получает ссылку после YouTube (schedule_telegram_links),
            # а не файлы тематических шортсов через Postiz.
            return 0
        if not self._platform_ok(platform, etype="long_video", eid=parent_id):
            return 0  # серия другого проекта — в эту сеть не публикуем
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
        if scope_roots:
            film = self.db.fetchone(
                "SELECT folder_path FROM long_videos WHERE id=?", (parent_id,))
            if film is None or not self._in_scope(film.get("folder_path"), scope_roots):
                return 0  # шортсы фильма вне «Папок для сканирования» не планируем

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
        # один шорт на слот ровно в 20:30; занятые слоты пропускаем (остаток -> «Остаток»)
        def _utc_minute_key(val) -> str:
            if val is None:
                return ""
            if isinstance(val, datetime):
                dt = val
            else:
                try:
                    dt = datetime.fromisoformat(str(val))
                except Exception:
                    return str(val)[:16]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")

        taken = set()
        for r in self.db.fetchall(
            "SELECT postiz_scheduled_for FROM entity_platform_status "
            "WHERE platform=? AND postiz_scheduled_for IS NOT NULL "
            "AND status IN ('scheduled','updating','published')",
            (platform,),
        ):
            ts = r["postiz_scheduled_for"]
            if ts:
                taken.add(_utc_minute_key(ts))
        now = self.clock.now()
        # P1-7 (как у фильмов): слот в прошлом Postiz публикует немедленно — не берём такие
        free_slots = [sl for sl in slots if sl > now and _utc_minute_key(sl) not in taken]
        # слоты, занятые в Postiz/n8n, тоже пропускаем — берём следующий свободный
        free_slots = [sl for sl in free_slots if not self._guard_busy(platform, sl)]
        assignments = list(zip(short_ids, free_slots, strict=False))

        pcfg = self.cfg.platforms[platform]
        if getattr(pcfg, "post_mode", "media") == "link":
            return 0
        if self.job is not None:
            self.job.set_total(max(self.job.state.total, len(assignments)))
        count = 0
        for sid, sched in assignments:
            if self.job is not None and self.job.cancelled:
                break
            if self._in_publish_cooldown("short", sid, platform):
                continue  # после сбоя не перебираем шортс каждый цикл
            short = next(s for s in shorts if s["id"] == sid)
            desc = template.format(
                description=short["description_text"] or "",
                link=release_url or self.cfg.link_update.placeholder_text,
            )
            content = {
                "title": short["title_text"] or "",
                "description": desc,
                "hashtags": short["hashtags_text"] or "",
                "cover": short.get("cover_path") or "",
            }
            path = self._pick_short_path(short, platform)
            if not path:
                continue
            # публикуем ровно в слот (без сдвигов на 25 минут)
            post = self._safe_publish("short", sid, platform, path, content, sched)
            if post:
                count += 1
            else:
                self._mark_publish_failed("short", sid, platform)
        return count



    def schedule_backlog(self, platform: str, start_date: str | None = None) -> int:
        """Публикует остаток (неопубликованные шортсы серий) по свободным слотам."""
        pcfg = self.cfg.platforms.get(platform)
        if not pcfg or not pcfg.enabled:
            return 0
        if getattr(pcfg, "post_mode", "media") == "link":
            # B: link-платформа (Telegram) публикует ссылку на YouTube, а не файл: иначе
            # «остаток серии» уходил в Postiz файлом (138 МБ → Bot API 413 / наш сторож 50 МБ).
            return 0
        shorts = self.db.fetchall(
            """
            SELECT s.id, s.video_path, s.platform_paths, s.parent_video_id, s.folder_path,
                   s.cover_path, s.title_text, s.description_text, s.hashtags_text
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
        slots = self._backlog_slots(platform, start_date=start_date)
        count = 0
        for s in shorts:
            if not self._platform_ok(platform, etype="short", eid=s["id"]):
                continue  # остаток другого проекта в эту сеть не ставим
            path = self._pick_short_path(s, platform)
            if not path:
                continue  # шортс принадлежит другой платформе (пакет платформ)
            if self._in_publish_cooldown("short", s["id"], platform):
                continue
            for slot in slots:
                if self._guard_busy(platform, slot):
                    continue
                ok, _ = self.safety.can_schedule(platform, self._slot_for_safety(slot), sched_settings.effective_daily_limit(self.db, self.cfg, platform))
                if not ok:
                    continue
                content = {
                    "title": s["title_text"] or "",
                    "description": s["description_text"] or "",
                    "hashtags": s["hashtags_text"] or "",
                    "cover": s.get("cover_path") or "",
                }
                post = self._safe_publish("short", s["id"], platform, path, content, slot)
                if post:
                    count += 1
                    break
                # P1-6: ошибка create — не перебираем остальные слоты и не грузим медиа снова
                self._mark_publish_failed("short", s["id"], platform)
                break
        return count

    def _bot_telegram(self) -> Any:
        """Издатель Bot API, если Telegram переведён на прямую отправку (иначе None)."""
        tcfg = self.cfg.platforms.get("telegram")
        tg = getattr(self, "telegram", None)
        if not tcfg or not getattr(tcfg, "enabled", True):
            return None
        if str(getattr(tcfg, "send_via", "postiz") or "postiz").lower() != "bot":
            return None
        if tg is None or not getattr(tg, "enabled", False):
            return None
        return tg

    def _telegram_post_html(self, etype: str, eid: int, url: str | None) -> str | None:
        """Текст поста в Telegram: хук, описание (как на YouTube), ссылка, хэштеги.

        Ссылку оставляем в тексте и её же отдаём как link_preview_options.url —
        иначе Telegram построит превью по первой ссылке из описания (плейлист).
        """
        from html import escape

        table = "long_videos" if etype == "long_video" else "shorts"
        item = self.db.fetchone(
            f"SELECT title_text, description_text, hashtags_text FROM {table} WHERE id=?", (eid,))
        if not item:
            return None
        title = escape(str(item["title_text"] or "").strip())
        desc = escape(str(item["description_text"] or "").strip())
        tags = escape(str(item["hashtags_text"] or "").strip())
        emoji = "🎬" if etype == "long_video" else "🔥"
        cta = "Полное видео на YouTube" if etype == "long_video" else "Полный выпуск на YouTube"
        blocks: list[str] = []
        if title:
            blocks.append(f"{emoji} <b>{title}</b>")
        if desc:
            blocks.append(desc)
        blocks.append(f"▶️ {cta}: {escape(url)}" if url
                      else "▶️ Ссылка появится после премьеры на YouTube")
        if tags and tags not in desc:
            blocks.append(tags)
        return "\n\n".join(blocks).strip()

    def send_due_telegram_posts(self) -> int:
        """Telegram (send_via=bot): отправить посты, у которых пришло время.

        Время = выход на YouTube + telegram_link_delay_min (лежит в
        postiz_scheduled_for). Пока ссылки нет — ждём release_url_timeout_min
        и потом отправляем без ссылки (как и режим Postiz).
        """
        tg = self._bot_telegram()
        if tg is None:
            return 0
        now = self.clock.now()
        wait_min = int(getattr(self.cfg.link_update, "release_url_timeout_min", 90) or 90)
        rows = self.db.fetchall(
            """
            SELECT entity_type, entity_id, postiz_scheduled_for
            FROM entity_platform_status
            WHERE platform='telegram' AND status='scheduled'
              AND (postiz_post_id IS NULL OR postiz_post_id='')
              AND postiz_scheduled_for IS NOT NULL AND postiz_scheduled_for <= ?
            ORDER BY postiz_scheduled_for
            """,
            (now.isoformat(),),
        )
        count = 0
        for r in rows:
            etype, eid = r["entity_type"], r["entity_id"]
            try:
                when = datetime.fromisoformat(str(r["postiz_scheduled_for"]))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=UTC)
            except Exception:
                logger.debug("telegram bot: плохое время у %s/%s", etype, eid, exc_info=True)
                when = now
            if self._in_publish_cooldown(etype, eid, "telegram"):
                continue
            yt = self.db.fetchone(
                "SELECT release_url FROM entity_platform_status "
                "WHERE entity_type=? AND entity_id=? AND platform='youtube' "
                "AND status='published' AND release_url IS NOT NULL",
                (etype, eid),
            )
            url = str(yt["release_url"]) if yt and yt["release_url"] else None
            if not url and (now - when) < timedelta(minutes=wait_min):
                continue  # премьера только что прошла — ждём ссылку от YouTube
            text = self._telegram_post_html(etype, eid, url)
            if not text:
                continue
            buttons = [{"text": "▶️ Смотреть на YouTube", "url": url}] if url else None
            try:
                pid = tg.send_post(text, buttons=buttons, preview_url=url)
            except Exception:
                logger.exception("telegram bot: отправка не удалась %s/%s", etype, eid)
                self._mark_publish_failed(etype, eid, "telegram")
                continue
            self.db.execute(
                "UPDATE entity_platform_status SET status='published', postiz_post_id=?, "
                "published_at=?, link_updated_at=COALESCE(link_updated_at, ?), last_error=NULL "
                "WHERE entity_type=? AND entity_id=? AND platform='telegram' "
                "AND (postiz_post_id IS NULL OR postiz_post_id='')",
                (pid, now.isoformat(), now.isoformat(), etype, eid),
            )
            self.db.log(etype, eid, "telegram", "bot_sent", pid)
            logger.info("telegram bot: отправлен %s/%s -> %s", etype, eid, pid)
            count += 1
        return count

    def _link_text(self, etype: str, eid: int, url: str | None) -> str | None:
        table = "long_videos" if etype == "long_video" else "shorts"
        item = self.db.fetchone(
            f"SELECT title_text, description_text FROM {table} WHERE id=?", (eid,))
        if not item:
            return None
        if url:
            tmpl = self.cfg.description_templates.get(
                "telegram_link", "{title}\n\n{description}\n\n▶ Смотреть на YouTube: {link}")
            return tmpl.format(title=item["title_text"] or "",
                               description=item["description_text"] or "",
                               link=url).strip()
        tmpl = self.cfg.description_templates.get(
            "telegram_link_no_link",
            "{title}\n\n{description}\n\n▶ Смотреть на YouTube — ссылка появится после премьеры")
        return tmpl.format(title=item["title_text"] or "",
                           description=item["description_text"] or "").strip()

    def schedule_telegram_links(self) -> int:
        """Telegram (post_mode=link): посты-ссылки в плане заранее, с плейсхолдером до премьеры."""
        tcfg = self.cfg.platforms.get("telegram")
        if not tcfg or not tcfg.enabled or getattr(tcfg, "post_mode", "media") != "link":
            return 0
        delay = int(getattr(self.cfg, "telegram_link_delay_min", 15) or 0)
        limit = sched_settings.effective_daily_limit(self.db, self.cfg, "telegram")
        count = 0
        # YouTube перепланировали -> двигаем время «ожидающей» Telegram-строки
        from datetime import datetime as _dt2
        for r in self.db.fetchall(
            """
            SELECT t.entity_type, t.entity_id, t.postiz_scheduled_for,
                   COALESCE(y.postiz_scheduled_for, y.published_at) AS yt_when
            FROM entity_platform_status t
            JOIN entity_platform_status y
              ON y.entity_type=t.entity_type AND y.entity_id=t.entity_id
             AND y.platform='youtube'
            WHERE t.platform='telegram' AND t.status='ready'
              AND t.last_error='waiting_for_youtube'
              AND COALESCE(y.postiz_scheduled_for, y.published_at) IS NOT NULL
            """
        ):
            try:
                base = _dt2.fromisoformat(str(r["yt_when"]))
            except Exception:
                continue
            new_when = (base + timedelta(minutes=delay)).isoformat()
            if str(r["postiz_scheduled_for"] or "") != new_when:
                self.db.execute(
                    "UPDATE entity_platform_status SET postiz_scheduled_for=? "
                    "WHERE entity_type=? AND entity_id=? AND platform='telegram'",
                    (new_when, r["entity_type"], r["entity_id"]),
                )
        rows = self.db.fetchall(
            """
            SELECT eps.entity_type, eps.entity_id, eps.status, eps.release_url,
                   COALESCE(eps.postiz_scheduled_for, eps.published_at) AS when_at
            FROM entity_platform_status eps
            WHERE eps.platform='youtube' AND eps.status IN ('scheduled','published')
              AND COALESCE(eps.postiz_scheduled_for, eps.published_at) IS NOT NULL
            ORDER BY when_at
            """,
        )
        for r in rows:
            etype, eid = r["entity_type"], r["entity_id"]
            if not self._platform_ok("telegram", etype=etype, eid=eid):
                continue  # сущность другого проекта в этот канал не ставим
            exists = self.db.fetchone(
                "SELECT 1 FROM entity_platform_status "
                "WHERE entity_type=? AND entity_id=? AND platform='telegram'",
                (etype, eid),
            )
            if exists:
                continue
            url = r["release_url"] if r["status"] == "published" else None
            try:
                from datetime import datetime as _dt
                yt_time = _dt.fromisoformat(str(r["when_at"]))
            except Exception:
                continue
            when = yt_time + timedelta(minutes=delay)
            if when <= self.clock.now():
                when = self.clock.now() + timedelta(minutes=1)
            if url:
                text = self._link_text(etype, eid, url)
                if not text:
                    continue
                if self._in_publish_cooldown(etype, eid, "telegram"):
                    continue
                # слот может быть занят другим постом канала — сдвигаем на 15 минут
                for _ in range(8):
                    if not self._guard_busy("telegram", when):
                        break
                    when = when + timedelta(minutes=15)
                else:
                    logger.info("telegram link (%s/%s): ближайшие слоты заняты", etype, eid)
                    continue
                ok, reason = self.safety.can_schedule("telegram", self._slot_for_safety(when), limit)
                if not ok:
                    logger.info("telegram link skip (%s/%s): %s", etype, eid, reason)
                    self._mark_publish_failed(etype, eid, "telegram")
                    continue
                content = {"title": "", "description": text, "hashtags": "",
                           "priority": "link"}
                post = self._safe_publish(etype, eid, "telegram", None, content, when)
                if post:
                    count += 1
                    self.db.execute(
                        "UPDATE entity_platform_status SET link_updated_at=? "
                        "WHERE entity_type=? AND entity_id=? AND platform='telegram'",
                        (self.clock.now().isoformat(), etype, eid),
                    )
            else:
                # видео ещё не вышло: показываем в плане, но НИЧЕГО не публикуем
                self.db.execute(
                    "INSERT OR IGNORE INTO entity_platform_status "
                    "(entity_type, entity_id, platform, status, postiz_scheduled_for, last_error) "
                    "VALUES (?, ?, 'telegram', 'ready', ?, 'waiting_for_youtube')",
                    (etype, eid, when.isoformat()),
                )
                count += 1
        return count

    def refresh_telegram_links(self) -> int:
        """После выхода видео обновляем Telegram-пост реальной ссылкой (пересоздаём)."""
        tcfg = self.cfg.platforms.get("telegram")
        if not tcfg or not tcfg.enabled or getattr(tcfg, "post_mode", "media") != "link":
            return 0
        rows = self.db.fetchall(
            """
            SELECT t.entity_type, t.entity_id, t.postiz_post_id, t.postiz_scheduled_for
            FROM entity_platform_status t
            WHERE t.platform='telegram' AND t.status IN ('scheduled','updating','ready')
              AND t.link_updated_at IS NULL
              AND EXISTS (
                SELECT 1 FROM entity_platform_status y
                WHERE y.entity_type=t.entity_type AND y.entity_id=t.entity_id
                  AND y.platform='youtube' AND y.status='published'
                  AND y.release_url IS NOT NULL
              )
            """,
        )
        count = 0
        for r in rows:
            etype, eid = r["entity_type"], r["entity_id"]
            yt = self.db.fetchone(
                "SELECT release_url FROM entity_platform_status "
                "WHERE entity_type=? AND entity_id=? AND platform='youtube' "
                "AND status='published' AND release_url IS NOT NULL",
                (etype, eid),
            )
            if not yt or not yt["release_url"]:
                continue
            if self._bot_telegram() is not None:
                # Отправляет наш бот (превью ролика сверху + кнопка): помечаем «ссылка
                # известна», а саму отправку сделает send_due_telegram_posts() вовремя.
                self.db.execute(
                    "UPDATE entity_platform_status SET link_updated_at=?, status='scheduled', "
                    "postiz_post_id=NULL, last_error=NULL "
                    "WHERE entity_type=? AND entity_id=? AND platform='telegram'",
                    (self.clock.now().isoformat(), etype, eid),
                )
                count += 1
                continue
            text = self._link_text(etype, eid, yt["release_url"])
            if not text:
                continue
            when = None
            if r["postiz_scheduled_for"]:
                try:
                    from datetime import datetime as _dt
                    when = _dt.fromisoformat(str(r["postiz_scheduled_for"]))
                except Exception:
                    when = None
            if when is None or when <= self.clock.now():
                when = self.clock.now() + timedelta(minutes=1)
            # L28: create new → persist → delete old; rollback on create fail
            old_id = r["postiz_post_id"]
            content = {"title": "", "description": text, "hashtags": ""}
            # Temporarily clear id so publish can create; keep old_id for rollback.
            # CAS: если строку уже забрал другой цикл (pid изменился) — не пересоздаём
            # ссылку второй раз, иначе в канале появляются дубли постов.
            taken = self.db.execute(
                "UPDATE entity_platform_status SET status='updating', postiz_post_id=NULL "
                "WHERE entity_type=? AND entity_id=? AND platform='telegram' "
                "AND postiz_post_id IS ?",
                (etype, eid, old_id),
            )
            if not taken:
                logger.info("telegram refresh: строку уже обновляет другой цикл %s/%s", etype, eid)
                continue
            post = None
            try:
                post = self._safe_publish(etype, eid, "telegram", None, content, when)
            except Exception:
                logger.exception("telegram refresh create failed %s/%s", etype, eid)
                post = None
            if post:
                if old_id:
                    try:
                        self.publisher.postiz.delete_post(str(old_id))
                    except Exception:
                        logger.warning("telegram refresh: не удалил старый пост %s", old_id)
                self.db.execute(
                    "UPDATE entity_platform_status SET link_updated_at=? "
                    "WHERE entity_type=? AND entity_id=? AND platform='telegram'",
                    (self.clock.now().isoformat(), etype, eid),
                )
                count += 1
            elif old_id:
                # rollback: restore old post id
                self.db.execute(
                    "UPDATE entity_platform_status SET status='scheduled', postiz_post_id=?, "
                    "last_error='refresh_failed' "
                    "WHERE entity_type=? AND entity_id=? AND platform='telegram'",
                    (old_id, etype, eid),
                )
        count += self._promote_waiting_without_url()
        return count

    def _promote_waiting_without_url(self) -> int:
        """Строки «ждёт выхода на YouTube» при уже вышедшем видео без ссылки — в отправку.

        Так бывает, когда публикация состоялась, но Postiz не отдал release_url (например
        видео загрузилось, а обложка не встала у неподтверждённого канала, см. StatusSync).
        Без этого строка висела в «ждёт выхода на YouTube» вечно.

        Только путь Bot API: саму отправку с плейсхолдером делает send_due_telegram_posts()
        (он же ждёт release_url_timeout_min и потом шлёт пост без ссылки).
        """
        if self._bot_telegram() is None:
            return 0
        wait_min = int(getattr(self.cfg.link_update, "release_url_timeout_min", 90) or 90)
        rows = self.db.fetchall(
            """
            SELECT t.entity_type, t.entity_id, t.postiz_scheduled_for
            FROM entity_platform_status t
            JOIN entity_platform_status y
              ON y.entity_type=t.entity_type AND y.entity_id=t.entity_id
             AND y.platform='youtube' AND y.status='published'
            WHERE t.platform='telegram' AND t.status='ready'
              AND t.last_error='waiting_for_youtube'
              AND (y.release_url IS NULL OR y.release_url='')
            """,
        )
        now = self.clock.now()
        count = 0
        for r in rows:
            when = None
            if r["postiz_scheduled_for"]:
                try:
                    when = datetime.fromisoformat(str(r["postiz_scheduled_for"]))
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=UTC)
                except Exception:
                    when = None
            if when is not None and (now - when) < timedelta(minutes=wait_min):
                continue  # премьера только что прошла — ещё ждём ссылку
            self.db.execute(
                "UPDATE entity_platform_status SET status='scheduled', last_error=NULL "
                "WHERE entity_type=? AND entity_id=? AND platform='telegram' "
                "AND status='ready' AND last_error='waiting_for_youtube'",
                (r["entity_type"], r["entity_id"]),
            )
            logger.info("telegram: %s/%s — видео вышло без ссылки, пост уйдёт с плейсхолдером",
                        r["entity_type"], r["entity_id"])
            count += 1
        return count

    def _backlog_slots(self, platform: str, days: int = 30,
                       start_date: str | None = None) -> list[datetime]:
        """Свободные слоты платформы: слот серии + обычные шортсы + тематические.

        P1-3: берём ЭФФЕКТИВНЫЕ настройки (override платформы/группы → конфиг → дефолты),
        иначе при любом override слоты бэклога не проходят `_is_canonical` и раскладка встаёт.
        """
        from datetime import timedelta

        from .slots import DAY_MAP, get_tz, local_to_utc, parse_time

        tz = get_tz(self.cfg.timezone)
        eff_long = sched_settings.effective(self.db, self.cfg, platform, "long")
        eff_sa = sched_settings.effective(self.db, self.cfg, platform, "standalone")
        eff_th = sched_settings.effective(self.db, self.cfg, platform, "thematic")

        def _days(spec: dict) -> set:
            return {DAY_MAP[str(d).lower()[:3]] for d in (spec.get("days") or [])
                    if str(d).lower()[:3] in DAY_MAP}

        long_days = _days(eff_long) or {DAY_MAP["tue"], DAY_MAP["fri"]}
        long_time = eff_long.get("time") or "16:00"
        sa_days = _days(eff_sa)
        sa_times = list(eff_sa.get("times") or [])
        th_time = eff_th.get("time") or "20:30"

        now = self.clock.now()
        local_today = now.astimezone(tz).date()
        if start_date:
            try:
                from datetime import date as _date
                y, m, d = (int(x) for x in start_date.split("-"))
                local_today = _date(y, m, d)
            except Exception:
                logger.warning("backlog: некорректная дата начала %r", start_date)
        local_today = max(local_today, now.astimezone(tz).date())
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

    def schedule_standalone_shorts(self, tail_manager=None, start_date: str | None = None,
                                   scope_roots: list | None = None) -> int:
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

        # L1: ready query per platform (NOT EXISTS filters eps.platform)
        count = 0
        for platform, pcfg in self.cfg.platforms.items():
            if not pcfg.enabled:
                continue
            if getattr(pcfg, "post_mode", "media") == "link":
                continue
            if tail_manager and tail_manager.should_pause_standalone(platform):
                continue
            ready = self.db.fetchall(
                """
                SELECT s.id, s.video_path, s.folder_path, s.platform_paths, s.title_text,
                       s.description_text, s.hashtags_text, s.cover_path
                FROM shorts s
                WHERE s.source = 'shortsmaker'
                  AND s.parent_video_id IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM entity_platform_status eps
                      WHERE eps.entity_type='short' AND eps.entity_id=s.id
                        AND eps.platform=?
                        AND eps.status IN ('scheduled','published','skipped')
                  )
                ORDER BY s.order_index, s.id
                LIMIT ?
                """,
                (platform, self.cfg.limits.max_posts_per_distribute),
            )
            if not ready:
                continue
            eff = sched_settings.effective(self.db, self.cfg, platform, "standalone")
            days = eff.get("days") or ["mon", "wed", "thu", "sat", "sun"]
            times = eff.get("times") or ["12:00", "18:00"]
            limit = sched_settings.effective_daily_limit(self.db, self.cfg, platform)
            exceptions = set(eff.get("exception_days") or [])
            weekday_set = {DAY_MAP[d.lower()[:3]] for d in days}
            if self.job is not None:
                self.job.set_total(self.job.state.total + len(ready))
            for short in ready:
                if self.job is not None and self.job.cancelled:
                    break
                if not self._in_scope(short.get("folder_path"), scope_roots):
                    continue  # отдельный шортс вне «Папок для сканирования» не планируем
                if not self._platform_ok(platform, folder=short.get("folder_path")):
                    continue  # шортс другого проекта в эту сеть не ставим
                if self._in_publish_cooldown("short", short["id"], platform):
                    continue
                cur = local_today
                placed = False
                failed = False
                for _ in range(28):
                    if cur.weekday() in weekday_set and cur.isoformat() not in exceptions:
                        for ts in times:
                            t = parse_time(ts)
                            candidate = local_to_utc(cur, t, self.cfg.timezone)
                            if candidate <= now:
                                continue
                            if self._guard_busy(platform, candidate):
                                continue
                            ok, _ = self.safety.can_schedule(platform, self._slot_for_safety(candidate), limit)
                            if ok:
                                content = {
                                    "title": short["title_text"] or "",
                                    "description": short["description_text"] or "",
                                    "hashtags": short["hashtags_text"] or "",
                                    "cover": short.get("cover_path") or "",
                                }
                                post = self._safe_publish(
                                    "short", short["id"], platform,
                                    self._pick_short_path(short, platform),
                                    content, candidate,
                                )
                                if post:
                                    count += 1
                                    placed = True
                                    if self.job is not None:
                                        self.job.tick(1, f"Обычный шортс #{short['id']}")
                                else:
                                    # P1-6: ошибка create — не перебираем дни и не грузим медиа заново
                                    failed = True
                                    self._mark_publish_failed("short", short["id"], platform)
                                break
                        if placed or failed:
                            break
                    cur += timedelta(days=1)
        return count
