from __future__ import annotations

import logging
import signal
import time
from datetime import UTC
from pathlib import Path
from typing import Any

from .http_server import start_http_server
from .metrics import Metrics
from .webapp_api import WebAppAPI

logger = logging.getLogger(__name__)


class Runner:
    """Long-running loop: watcher → schedule → sync → reconcile → backup by intervals."""

    def __init__(self, comps: dict[str, Any], dry_run: bool = False, health_port: int = 8080):
        self.comps = comps
        self.cfg = comps["cfg"]
        self.dry_run = dry_run
        self._stop = False
        self._miss_streak: dict[str, int] = {}
        self._cycle_fail_streak = 0
        self._miss_error_threshold = 3  # R8: N consecutive misses → error
        db_path = Path(comps["db"].path)
        self.metrics = comps.get("metrics") or Metrics(db_path.parent / "metrics.json")
        webapi = WebAppAPI(comps)
        self._http = start_http_server(
            health_port,
            lambda: {"ok": True, "dry_run": dry_run, **self.metrics.snapshot()},
            webapp_handler=webapi.handle,
        )

    def stop(self, *_args) -> None:
        logger.info("Shutdown requested")
        self._stop = True

    def run_forever(self) -> None:
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        last_watch = last_sync = last_recon = last_backup = last_test_cleanup = time.monotonic()
        last_daily_ahead_date: str | None = None
        w_int = self.cfg.watcher_interval_sec
        s_int = self.cfg.status_sync_interval_sec
        r_int = self.cfg.reconciliation_interval_hours * 3600
        b_int = self.cfg.backup.interval_hours * 3600
        m_int = 86400 if self.cfg.manual_uploads.schedule_scan == "daily" else 0
        last_manual = time.monotonic()  # next manual scan after the interval

        logger.info(
            "Runner started (watch=%ss sync=%ss recon=%sh backup=%sh dry_run=%s)",
            w_int, s_int, self.cfg.reconciliation_interval_hours,
            self.cfg.backup.interval_hours, self.dry_run,
        )

        while not self._stop:
            now = time.monotonic()
            try:
                if now - last_watch >= w_int:
                    self._cycle_watch()
                    last_watch = now
                if now - last_sync >= s_int:
                    self._cycle_sync()
                    last_sync = now
                if now - last_recon >= r_int:
                    self._cycle_recon()
                    last_recon = now
                if now - last_backup >= b_int:
                    self._cycle_backup()
                    last_backup = now
                if m_int and now - last_manual >= m_int:
                    self._cycle_manual()
                    last_manual = now
                if now - last_test_cleanup >= 3600:  # P1.3: раз в час
                    self._cycle_test_cleanup()
                    last_test_cleanup = now
                da = getattr(self.cfg, "daily_ahead", None)
                if da is not None and getattr(da, "enabled", False):
                    last_daily_ahead_date = self._maybe_daily_ahead(last_daily_ahead_date)
            except Exception as e:
                self.metrics.incr("errors")
                self.metrics.set("last_error", str(e))
                self.metrics.flush()
                self._cycle_fail_streak += 1
                # R6: exponential backoff on cycle errors (cap 5 min)
                delay = min(300, 2 ** min(self._cycle_fail_streak, 8))
                logger.exception("Cycle error (streak=%s, backoff=%ss)", self._cycle_fail_streak, delay)
                time.sleep(delay)
                continue
            else:
                self._cycle_fail_streak = 0
            time.sleep(1)

        logger.info("Runner stopped")

    def _cycle_watch(self) -> None:
        from .overflow import move_excess_shorts
        stats = self.comps["watcher"].scan()
        logger.info("Watch: %s", stats)
        parents = self.comps["db"].fetchall(
            "SELECT DISTINCT parent_video_id FROM shorts WHERE parent_video_id IS NOT NULL"
        )
        for p in parents:
            move_excess_shorts(
                self.comps["db"], self.cfg, self.comps["clock"], p["parent_video_id"]
            )
        from . import sched_settings
        roots = [str(r) for r in self.comps["watcher"].effective_roots()]
        if sched_settings.scheduling_mode(self.comps["db"]) == "auto":
            n = self.comps["scheduler"].schedule_long_videos(scope_roots=roots)
            n2 = self.comps["scheduler"].schedule_standalone_shorts(
                self.comps["tail"], scope_roots=roots)
        else:
            n = n2 = 0
        pubs = self.comps["db"].fetchall(
            "SELECT entity_id, platform FROM entity_platform_status "
            "WHERE entity_type='long_video' AND status IN ('published','scheduled')"
        )
        nt = 0
        for r in pubs:
            nt += self.comps["scheduler"].schedule_thematic_shorts(
                r["entity_id"], r["platform"], scope_roots=roots
            )
        nl = self.comps["scheduler"].schedule_telegram_links()
        if nl:
            logger.info("Telegram link posts scheduled: %s", nl)
        nref = self.comps["scheduler"].refresh_telegram_links()
        if nref:
            logger.info("Telegram link posts refreshed: %s", nref)
        nsent = self.comps["scheduler"].send_due_telegram_posts()
        if nsent:
            logger.info("Telegram posts sent via Bot API: %s", nsent)
        self.metrics.incr("scheduled_short", nl)
        postiz = self.comps.get("postiz")
        if postiz is not None and hasattr(postiz, "orphan_media_ids"):
            orphans = postiz.orphan_media_ids()
            if orphans:
                logger.warning("Postiz orphan media (не привязаны к постам): %s", len(orphans))
                if hasattr(postiz, "clear_orphan_media"):
                    postiz.clear_orphan_media()
        self.metrics.incr("scheduled_long", n)
        self.metrics.incr("scheduled_short", n2 + nt)
        if n or n2 or nt:
            logger.info("Scheduled long=%s standalone=%s thematic=%s", n, n2, nt)
        self._backlog_check()
        self.metrics.tick_cycle()

    def _backlog_check(self) -> None:
        """Спрашиваем/распределяем остаток шортсов серии перед слотом серии."""
        bl = self.comps.get("backlog")
        if not bl:
            return
        for platform, pcfg in self.cfg.platforms.items():
            if not getattr(pcfg, "enabled", False):
                continue
            try:
                slot = bl.needs_question(platform)
                if slot:
                    bl.ask(platform, slot)
                    continue
                if bl.awaiting(platform):
                    if bl.auto_default(platform):
                        logger.info("Backlog auto-distributed on %s", platform)
                        continue
                    rslot = bl.should_remind(platform)
                    if rslot:
                        bl.mark_reminded(platform, rslot)
                    continue
                if bl.missed_default(platform):
                    logger.info("Backlog distributed after missed window on %s", platform)
            except Exception:
                logger.exception("backlog check failed for %s", platform)

    def _cycle_test_cleanup(self) -> None:
        from .test_publish import cleanup_expired_test_posts

        try:
            n = cleanup_expired_test_posts(self.comps)
        except Exception:
            logger.warning("test cleanup failed", exc_info=True)
            return
        if n:
            self.metrics.incr("test_cancelled", n)

    def _cycle_sync(self) -> None:
        n = self.comps["status_sync"].sync()
        # accelerated pass for near-term posts
        n2 = self.comps["status_sync"].sync(fresh_only=True)
        self.comps["link_upd"].check_missing_urls()
        # refresh thematic descriptions when URL just appeared
        pubs = self.comps["db"].fetchall(
            "SELECT entity_id, platform FROM entity_platform_status "
            "WHERE entity_type='long_video' AND status='published' AND release_url IS NOT NULL"
        )
        for r in pubs:
            u = self.comps["link_upd"].refresh_thematic_after_url(
                r["entity_id"], r["platform"], self.comps["scheduler"]
            )
            if u:
                logger.info("Refreshed thematic with URL: %s", u)
        for p in self.cfg.platforms:
            self.comps["tail"].sync_new_long(p)
            self.comps["tail"].check_soft_enter(p)
        self.comps["tail"].expire_pending_questions()
        if n or n2:
            logger.info("Status sync updates: %s (fresh %s)", n, n2)
        self.metrics.incr("sync_updates", n + n2)
        self.metrics.flush()

    def _cycle_recon(self) -> None:
        r = self.comps["recon"].run()
        logger.info("Reconciliation: %s", r)
        missing = int(r.get("missing") or 0)
        orphans = int(r.get("orphans") or 0)
        if not missing:
            return
        lines = [
            "⚠️ Сверка с Postiz нашла расхождение:",
            f"• {missing} запланированных постов пропали из Postiz "
            "(в нашей базе они есть, а в Postiz их нет).",
        ]
        if orphans:
            lines.append(
                f"• Ещё {orphans} пост(ов) есть в Postiz, но их нет в нашей базе "
                "(возможно, созданы вручную или остались от старых правок)."
            )
        lines.append(
            "Что делать: открой панель → «Очередь» и «Действия» → «Разложить по слотам» — "
            "система поставит пропавшие посты заново."
        )
        self.comps["tg"].broadcast("\n".join(lines))

    def _cycle_manual(self) -> None:
        manual = self.comps.get("manual")
        sources = self.comps.get("manual_sources") or {}
        if not manual or not self.cfg.manual_uploads.enabled or not sources:
            return
        import json as _json

        stats = manual.scan_all(sources)
        self.comps["db"].set_setting("manual_last_scan", _json.dumps(
            {"at": self.comps["clock"].now().isoformat(), "stats": stats}))
        logger.info("Manual scan: %s", stats)

    def _cycle_backup(self) -> None:
        from pathlib import Path

        from .backup import run_backup
        db_path = Path(self.comps["db"].path)
        bdir = db_path.parent.parent / "backups"
        path = run_backup(self.comps["db"], self.cfg, bdir)
        if path:
            logger.info("Backup: %s", path)

    def _maybe_daily_ahead(self, last_run_date: str | None) -> str | None:
        """Run daily_ahead once per local calendar day at configured hour:minute."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        da = self.cfg.daily_ahead
        try:
            tz = ZoneInfo(self.cfg.timezone or "Europe/Moscow")
        except Exception:
            tz = ZoneInfo("UTC")
        now_local = datetime.now(tz)
        today_s = now_local.date().isoformat()
        if last_run_date == today_s:
            return last_run_date
        if (now_local.hour, now_local.minute) < (int(da.hour), int(da.minute)):
            return last_run_date
        try:
            self._cycle_daily_ahead()
        except Exception:
            logger.exception("daily_ahead cycle failed")
            return last_run_date
        return today_s

    def _cycle_daily_ahead(self) -> None:
        """Collect slots for today+tomorrow without external_id; upload via module:youtube."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from .daily_ahead import AheadItem, plan_horizon, run_daily_ahead
        from .platforms import default_registry, resolve_engine

        da = self.cfg.daily_ahead
        eng = str(self.cfg.engine_for("youtube") or "")
        try:
            resolved = resolve_engine(eng)
        except ValueError:
            resolved = None
        youtube_module = None
        if resolved is not None and resolved.kind == "module" and resolved.module_id:
            reg = default_registry()
            if reg.has(resolved.module_id):
                broker = self.comps.get("broker")
                pcfg = self.cfg.platforms.get("youtube")
                iid = getattr(pcfg, "integration_id", "") or "" if pcfg else ""

                def _tp(p: str = "youtube", b=broker, i: str = iid) -> str:
                    if b is None:
                        return ""
                    try:
                        return str((b.get(p, i) or {}).get("token") or "")
                    except Exception:
                        return ""

                youtube_module = reg.create(
                    resolved.module_id,
                    token_provider=_tp,
                    cfg=self.cfg,
                    dry_run=bool(da.dry_run) or self.dry_run,
                    http=None,
                )

        try:
            tz = ZoneInfo(self.cfg.timezone or "Europe/Moscow")
        except Exception:
            tz = ZoneInfo("UTC")
        today = datetime.now(tz).date()
        horizon = plan_horizon(today, days=int(da.days or 2))
        horizon_set = {d.isoformat() for d in horizon}

        rows = self.comps["db"].fetchall(
            """
            SELECT eps.entity_type, eps.entity_id, eps.postiz_post_id, eps.postiz_scheduled_for,
                   eps.status
            FROM entity_platform_status eps
            WHERE eps.platform='youtube'
              AND eps.status IN ('ready', 'scheduled')
              AND eps.postiz_scheduled_for IS NOT NULL
            """
        )
        items: list = []
        for r in rows:
            sched = r["postiz_scheduled_for"]
            try:
                dt = datetime.fromisoformat(str(sched))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                local_d = dt.astimezone(tz).date().isoformat()
            except Exception:
                continue
            if local_d not in horizon_set:
                continue
            if r["postiz_post_id"]:
                items.append(AheadItem(path="", title="", slot=dt, external_id=str(r["postiz_post_id"])))
                continue
            et, eid = r["entity_type"], r["entity_id"]
            if et == "long_video":
                row = self.comps["db"].fetchone(
                    "SELECT title, wide_path FROM long_videos WHERE id=?", (eid,),
                )
                path = (row["wide_path"] if row else None) or ""
                title = (row["title"] if row else "") or ""
            else:
                row = self.comps["db"].fetchone(
                    "SELECT title, path FROM shorts WHERE id=?", (eid,),
                )
                path = (row["path"] if row else None) or ""
                title = (row["title"] if row else "") or ""
            if not path:
                continue
            items.append(AheadItem(path=path, title=title, slot=dt, external_id=None))

        result = run_daily_ahead(items, youtube_module, dry_run=bool(da.dry_run) or self.dry_run)
        logger.info(
            "daily_ahead: uploaded=%s skipped=%s errors=%s dry_run=%s",
            result.uploaded, result.skipped, len(result.errors or []),
            bool(da.dry_run) or self.dry_run,
        )
        if result.errors:
            for err in result.errors[:10]:
                logger.warning("daily_ahead error: %s", err)

