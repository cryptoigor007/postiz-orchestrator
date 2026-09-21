from __future__ import annotations

import logging
import signal
import time
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

        last_watch = last_sync = last_recon = last_backup = last_test_cleanup = 0.0
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
        if sched_settings.scheduling_mode(self.comps["db"]) == "auto":
            n = self.comps["scheduler"].schedule_long_videos()
            n2 = self.comps["scheduler"].schedule_standalone_shorts(self.comps["tail"])
        else:
            n = n2 = 0
        pubs = self.comps["db"].fetchall(
            "SELECT entity_id, platform FROM entity_platform_status "
            "WHERE entity_type='long_video' AND status IN ('published','scheduled')"
        )
        nt = 0
        for r in pubs:
            nt += self.comps["scheduler"].schedule_thematic_shorts(
                r["entity_id"], r["platform"]
            )
        nl = self.comps["scheduler"].schedule_telegram_links()
        if nl:
            logger.info("Telegram link posts scheduled: %s", nl)
        nref = self.comps["scheduler"].refresh_telegram_links()
        if nref:
            logger.info("Telegram link posts refreshed: %s", nref)
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
