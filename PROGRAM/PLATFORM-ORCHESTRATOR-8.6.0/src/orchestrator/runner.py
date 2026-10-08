from __future__ import annotations

import logging
import os
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
        from .ops_health import OpsHealth
        self.ops_health = comps.get("ops_health") or OpsHealth(
            db=comps["db"], cfg=self.cfg, token_store=comps.get("token_lifecycle")
        )
        comps["ops_health"] = self.ops_health
        webapi = WebAppAPI(comps)
        from .webhook_ingress import WebhookIngress
        self._webhook = WebhookIngress(comps)
        self._http = start_http_server(
            health_port,
            self._health_payload,
            webapp_handler=webapi.handle,
            webhook_handler=self._webhook.handle,
        )


    def _health_payload(self) -> dict:
        """Deep health: process ok + db ping + tokens dir readable."""
        from pathlib import Path as _P
        snap = self.metrics.snapshot() if self.metrics else {}
        out: dict = {"ok": True, "dry_run": self.dry_run, **snap}
        sup = self.comps.get("provider_supervisor")
        access = self.comps.get("provider_access")
        if access is not None:
            try:
                out["provider_access"] = access.snapshot_all()
            except Exception:
                out["provider_access"] = {}
        if sup is not None:
            try:
                out["provider_health"] = sup.snapshot()
            except Exception:
                out["provider_health"] = {}
        try:
            self.comps["db"].fetchone("SELECT 1 AS ok")
            out["db"] = "ok"
        except Exception as e:
            out["db"] = f"error:{e}"
            out["ok"] = False
        try:
            tdir = _P("tokens")
            out["tokens_dir"] = str(tdir)
            out["tokens_readable"] = tdir.is_dir()
            if tdir.is_dir():
                out["token_files"] = len(
                    [p for p in tdir.iterdir() if p.suffix in (".json", ".jsonl")]
                )
            else:
                out["tokens_readable"] = False
        except Exception as e:
            out["tokens_error"] = str(e)
        out["cycle_fail_streak"] = getattr(self, "_cycle_fail_streak", 0)
        # Distinguish liveness from readiness: a provider outage must not make the
        # daemon itself unhealthy, but should be visible in provider_health.
        states = list((out.get("provider_health") or {}).values())
        out["degraded_provider_count"] = sum(1 for x in states if x.get("state") in ("degraded", "open"))
        try:
            out["ops"] = self.ops_health.snapshot()
        except Exception as e:
            out["ops"] = {"ready": False, "error": str(e)}
        out["ready"] = bool(out.get("db") == "ok" and not out.get("stopping") and out.get("ops", {}).get("ready", False))
        out["stopping"] = bool(getattr(self, "_stop", False))
        # Recompute readiness after stopping flag is known.
        out["ready"] = bool(out.get("db") == "ok" and not out.get("stopping") and out.get("ops", {}).get("ready", False))
        return out

    def stop(self, *_args) -> None:
        logger.info("Shutdown requested")
        self._stop = True

    def run_forever(self) -> None:
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        last_watch = last_sync = last_recon = last_backup = last_test_cleanup = time.monotonic()
        last_oauth_cleanup = time.monotonic()
        last_token_refresh = time.monotonic()
        last_remote_scan = last_claims = last_b2 = last_ig_finalize = time.monotonic()
        last_daily_ahead_date: str | None = None
        last_provider_health = time.monotonic()
        last_outbox = time.monotonic()
        last_jobs = time.monotonic()
        last_recovery = time.monotonic()
        last_media_cleanup = time.monotonic()
        last_webhooks = time.monotonic()
        worker_id = f"runner-{os.getpid()}"
        last_consistency = time.monotonic()
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
                if now - last_oauth_cleanup >= 3600:
                    self._cycle_oauth_cleanup()
                    last_oauth_cleanup = now
                if now - last_token_refresh >= 300:
                    self._cycle_token_refresh()
                    last_token_refresh = now
                if now - last_remote_scan >= 3600:
                    self._cycle_remote_scan()
                    last_remote_scan = now
                if now - last_claims >= 1800:
                    self._cycle_claims()
                    last_claims = now
                if now - last_b2 >= 3600:
                    self._cycle_b2_cleanup()
                    last_b2 = now
                if now - last_ig_finalize >= 120:
                    self._cycle_ig_finalize()
                    self._cycle_local_schedule_due()
                    last_ig_finalize = now
                if now - last_provider_health >= 30:
                    self._cycle_provider_health()
                    self._cycle_provider_access()
                    last_provider_health = now
                if now - last_outbox >= 15:
                    self._cycle_outbox()
                    last_outbox = now
                if now - last_jobs >= 5:
                    self._cycle_durable_jobs(worker_id)
                    last_jobs = now
                if now - last_recovery >= 60:
                    self._cycle_publish_recovery()
                    last_recovery = now
                if now - last_media_cleanup >= 3600:
                    self._cycle_media_cleanup()
                    last_media_cleanup = now
                if now - last_webhooks >= 10:
                    self._cycle_webhooks()
                    last_webhooks = now
                consistency_min = max(5, int(os.getenv("ORCH_CONSISTENCY_INTERVAL_MIN", "60") or 60))
                if now - last_consistency >= consistency_min * 60:
                    self._cycle_consistency()
                    last_consistency = now
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
                # OBS-01: alert operator when streak hits threshold
                if self._cycle_fail_streak in (3, 10, 30):
                    self._alert_cycle_fail(str(e))
                time.sleep(delay)
                continue
            else:
                self._cycle_fail_streak = 0
            time.sleep(1)

        logger.info("Runner stopped")


    def _alert_cycle_fail(self, err: str) -> None:
        """Notify Telegram allowlist when runner cycle fails repeatedly."""
        msg = (
            f"⚠️ Orchestrator cycle_fail_streak={self._cycle_fail_streak}\n"
            f"{(err or '')[:300]}"
        )
        bot = self.comps.get("tg") or self.comps.get("telegram_bot") or self.comps.get("bot")
        try:
            if bot is not None and hasattr(bot, "broadcast"):
                bot.broadcast(msg)
            elif bot is not None and hasattr(bot, "send"):
                cfg = getattr(bot, "cfg", None)
                ids = []
                if cfg is not None:
                    ids = list(getattr(getattr(cfg, "telegram", None), "allowed_chat_ids", None) or [])
                for cid in ids[:5]:
                    bot.send(int(cid), msg)
            else:
                logger.warning("cycle_fail alert (no bot): %s", msg.replace("\n", " | "))
        except Exception:
            logger.exception("cycle_fail alert failed")

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
        # platform orphan media cleanup removed (module path only).
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
                configured_account = str(getattr(pcfg, "account_id", "") or "").strip()
                rows = self.comps["db"].fetchall(
                    "SELECT DISTINCT account_id FROM entity_platform_status "
                    "WHERE platform=? AND account_id IS NOT NULL AND account_id!=''",
                    (platform,),
                )
                account_ids = sorted({
                    str(r.get("account_id") or "").strip()
                    for r in rows or []
                    if str(r.get("account_id") or "").strip()
                })
                if configured_account:
                    account_ids = sorted(set(account_ids) | {configured_account})
                if not account_ids:
                    account_ids = [""]

                for account_id in account_ids:
                    try:
                        scope = f" {platform}[{account_id}]" if account_id else f" {platform}"
                        slot = bl.needs_question(platform, account_id=account_id)
                        if slot:
                            bl.ask(platform, slot, account_id=account_id)
                            continue
                        if bl.awaiting(platform, account_id=account_id):
                            if bl.auto_default(platform, account_id=account_id):
                                logger.info("Backlog auto-distributed on%s", scope)
                                continue
                            rslot = bl.should_remind(platform, account_id=account_id)
                            if rslot:
                                bl.mark_reminded(platform, rslot, account_id=account_id)
                            continue
                        if bl.missed_default(platform, account_id=account_id):
                            logger.info("Backlog distributed after missed window on%s", scope)
                    except Exception:
                        logger.exception("backlog check failed for %s[%s]", platform, account_id or "legacy")
            except Exception:
                logger.exception("backlog account discovery failed for %s", platform)

    def _cycle_token_refresh(self) -> None:
        store = self.comps.get("token_lifecycle")
        if store is None:
            return
        try:
            for platform, pcfg in (self.cfg.platforms or {}).items():
                if not getattr(pcfg, "enabled", False):
                    continue
                account_id = str(getattr(pcfg, "account_id", "") or "")
                if not account_id:
                    continue
                result = store.refresh_expiring(platform, account_id, skew_sec=600)
                if result == "refreshed":
                    logger.info("token refresh ok %s[%s]", platform, account_id)
                elif result.startswith("failed:"):
                    logger.warning("token refresh failed %s[%s]: %s", platform, account_id, result)
        except Exception:
            logger.exception("token refresh cycle failed")

    def _cycle_oauth_cleanup(self) -> None:
        try:
            from .oauth.sessions import OAuthSessionStore
            n = OAuthSessionStore(self.comps["db"]).cleanup_expired()
            if n:
                logger.info("OAuth session cleanup removed %s stale sessions", n)
        except Exception:
            logger.exception("OAuth session cleanup failed")

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
        recon = self.comps.get("recon")
        if recon is None:
            return
        r = recon.run()
        logger.info("Reconciliation: %s", r)
        missing = int(r.get("missing") or 0)
        orphans = int(r.get("orphans") or 0)
        if not missing:
            return
        lines = [
            "⚠️ Module reconciliation found drift:",
            f"• {missing} scheduled rows missing on platform "
            "(present in local DB, absent remotely).",
        ]
        if orphans:
            lines.append(
                f"• {orphans} remote item(s) not tracked in local DB "
                "(manual uploads or legacy leftovers)."
            )
        lines.append(
            "Action: open panel → Queue → Actions → Reschedule slots."
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


    def _cycle_remote_scan(self) -> None:
        """Periodic remote inventory scan (module list_remote)."""
        try:
            from .remote_scan.service import RemoteScanService
            from .platforms import default_registry
            reg = self.comps.get("module_registry") or default_registry()
            svc = RemoteScanService(
                self.comps["db"], self.cfg, module_registry=reg,
                media_host=self.comps.get("media_host"),
            )
            results = []
            for plat, pcfg in (self.cfg.platforms or {}).items():
                if not getattr(pcfg, "enabled", False):
                    continue
                results.append(svc.scan_platform(plat, account_id=str(getattr(pcfg, "account_id", "") or "")))
            logger.info("remote_scan: %s", results)
        except Exception:
            logger.warning("remote_scan failed", exc_info=True)

    def _cycle_claims(self) -> None:
        """Claims checkpoint K hours before slot."""
        try:
            from .claims import run_claims_check
            from .platforms import default_registry
            yt = None
            reg = self.comps.get("module_registry") or default_registry()
            try:
                if reg is not None and reg.has("youtube"):
                    from .auth_tokens import token_provider_for
                    yt = reg.create(
                        "youtube",
                        dry_run=self.dry_run,
                        cfg=self.cfg,
                        token_provider=token_provider_for("youtube"),
                        media_host=self.comps.get("media_host"),
                        account_id=str(getattr(getattr(self.cfg, "platforms", {}).get("youtube"), "account_id", "") or ""),
                    )
            except Exception:
                logger.debug("youtube module create for claims failed", exc_info=True)
                yt = None
            hours = 6.0
            try:
                hours = float(getattr(getattr(self.cfg, "claims", None), "hours_before", 6) or 6)
            except Exception:
                hours = 6.0
            res = run_claims_check(
                self.comps["db"],
                clock=self.comps.get("clock"),
                youtube_module=yt,
                hours_before=hours,
                notifier=self.comps.get("tg"),
                account_id=str(getattr(getattr(self.cfg, "platforms", {}).get("youtube"), "account_id", "") or ""),
            )
            logger.info(
                "claims: checked=%s claimed=%s",
                getattr(res, "checked", 0), getattr(res, "claimed", 0),
            )
        except Exception:
            logger.warning("claims cycle failed", exc_info=True)

    def _cycle_b2_cleanup(self) -> None:
        """B2 media_host TTL cleanup."""
        try:
            host = self.comps.get("media_host")
            if host is None:
                from .media_host.b2 import create_media_host
                host = create_media_host(dry_run=self.dry_run, db=self.comps["db"])
            n = host.cleanup_expired()
            if n:
                logger.info("b2 TTL cleanup: deleted %s", n)
        except Exception:
            logger.debug("b2 cleanup failed", exc_info=True)



    def _cycle_provider_health(self) -> None:
        """Alert on provider circuit transitions without failing the core loop."""
        sup = self.comps.get("provider_supervisor")
        if sup is None:
            return
        try:
            snap = sup.snapshot()
            tg = self.comps.get("tg")
            db = self.comps.get("db")
            if not db:
                return
            for key, item in snap.items():
                state = str(item.get("state") or "unknown")
                if state not in {"open", "degraded", "healthy", "half_open"}:
                    continue
                prev_key = f"provider_health_prev:{key}"
                prev = db.get_setting(prev_key, "")
                if prev == state:
                    continue
                db.set_setting(prev_key, state)
                if tg:
                    if state in {"open", "degraded"} and (prev == "healthy" or (not prev and item.get("last_error"))):
                        tg.broadcast(f"⚠️ {item.get('provider')}[{item.get('account_id') or '-'}] provider health: {state}. {item.get('last_error') or ''}"[:1000])
                    elif state == "healthy" and prev in {"open", "degraded", "half_open"}:
                        tg.broadcast(f"✅ {item.get('provider')}[{item.get('account_id') or '-'}] provider recovered")
        except Exception:
            logger.debug("provider health cycle failed", exc_info=True)


    def _cycle_provider_access(self) -> None:
        """Probe configured provider module auth/capability state without publishing."""
        store = self.comps.get("provider_access")
        reg = self.comps.get("module_registry")
        if store is None or reg is None:
            return
        try:
            from .auth_tokens import token_provider_for
            for platform, pcfg in (self.cfg.platforms or {}).items():
                if not getattr(pcfg, "enabled", False) or not reg.has(platform):
                    continue
                account_id = str(getattr(pcfg, "account_id", "") or "")
                try:
                    mod = reg.create(platform, cfg=self.cfg, dry_run=self.dry_run,
                                     token_provider=token_provider_for(platform),
                                     account_id=account_id,
                                     media_host=self.comps.get("media_host"))
                    auth = mod.auth_status()
                    new_state = "CONNECTED" if auth.ok else "NOT_CONFIGURED"
                    prev_state = db.get_setting(f"provider_access_prev:{platform}::{account_id}", "") if db else ""
                    store.upsert(__import__("orchestrator.provider_access", fromlist=["ProviderAccessSnapshot"]).ProviderAccessSnapshot(
                        provider=platform, account_id=account_id,
                        credentials_ok=bool(auth.ok), token_ok=bool(auth.ok),
                        account_ok=bool(auth.account),
                        scopes_ok=bool(getattr(auth, "scopes", [])),
                        media_host_ok=bool(self.comps.get("media_host") is not None or getattr(getattr(mod, "manifest", None), "media_transfer", "") != "pull_from_url"),
                        state=new_state,
                        details=str(getattr(auth, "details", ""))[:1800],
                    ))
                    if db and prev_state != new_state:
                        db.set_setting(f"provider_access_prev:{platform}::{account_id}", new_state)
                        tg = self.comps.get("tg")
                        if tg and prev_state and new_state != prev_state:
                            if new_state != "CONNECTED":
                                tg.broadcast(f"⚠️ {platform}[{account_id or '-'}] access state: {new_state}. {getattr(auth, 'details', '')}"[:1000])
                            elif prev_state != "CONNECTED":
                                tg.broadcast(f"✅ {platform}[{account_id or '-'}] access recovered")
                except Exception as exc:
                    new_state = "DEGRADED"
                    prev_state = db.get_setting(f"provider_access_prev:{platform}::{account_id}", "") if db else ""
                    store.upsert(__import__("orchestrator.provider_access", fromlist=["ProviderAccessSnapshot"]).ProviderAccessSnapshot(
                        provider=platform, account_id=account_id, state=new_state, details=str(exc)[:1800]))
                    if db and prev_state != new_state:
                        db.set_setting(f"provider_access_prev:{platform}::{account_id}", new_state)
                        tg = self.comps.get("tg")
                        if tg and prev_state and prev_state != new_state:
                            tg.broadcast(f"⚠️ {platform}[{account_id or '-'}] access degraded: {exc}"[:1000])
        except Exception:
            logger.debug("provider access cycle failed", exc_info=True)

    def _cycle_consistency(self) -> None:
        """Reconcile authoritative provider state without coupling failures across providers."""
        sweeper = self.comps.get("consistency")
        if sweeper is None:
            return
        db = self.comps.get("db")
        if db is None:
            return
        try:
            targets = db.fetchall(
                "SELECT platform, account_id FROM provider_access WHERE live_ok=1 "
                "UNION SELECT platform, account_id FROM entity_platform_status "
                "WHERE external_id IS NOT NULL AND external_id!='' "
                "GROUP BY platform, account_id"
            )
            for row in targets or []:
                platform = str(row.get("platform") or "").strip().lower()
                account_id = str(row.get("account_id") or "")
                if not platform:
                    continue
                try:
                    result = sweeper.sweep(platform, account_id, limit=100)
                    if result.get("repaired") or result.get("conflicts"):
                        logger.warning("consistency %s[%s]: %s", platform, account_id or "-", result)
                except Exception:
                    logger.exception("consistency sweep failed %s[%s]", platform, account_id or "-")
        except Exception:
            logger.debug("consistency target discovery failed", exc_info=True)

    def _cycle_webhooks(self) -> None:
        processor = self.comps.get("webhook_processor")
        if processor is None:
            return
        try:
            result = processor.run(limit=50)
            stale = processor.reconcile_subscriptions(stale_after_sec=3600) if hasattr(processor, "reconcile_subscriptions") else 0
            if result.processed or result.retried or result.dead or result.repaired or stale:
                logger.info("webhooks: %s stale_subscriptions=%s", result, stale)
        except Exception:
            logger.exception("webhook processing cycle failed")

    def _cycle_media_cleanup(self) -> None:
        manager = self.comps.get("media_transfer")
        if manager is None:
            return
        try:
            n = manager.cleanup_orphans(older_than_sec=86400)
            if n:
                logger.info("media orphan cleanup: %s", n)
        except Exception:
            logger.exception("media orphan cleanup failed")

    def _cycle_publish_recovery(self) -> None:
        recovery = self.comps.get("publish_recovery")
        if recovery is None:
            return
        try:
            result = recovery.run(limit=50)
            if result.repaired or result.ambiguous or result.failed:
                logger.warning("publish attempt recovery: %s", result)
        except Exception:
            logger.exception("publish attempt recovery failed")

    def _cycle_durable_jobs(self, worker_id: str) -> None:
        """C2: execute durable jobs; JobRegistry is presentation-only."""
        jobs = self.comps.get("durable_jobs")
        if not jobs:
            return
        handlers = self.comps.get("job_handlers") or {}
        try:
            jobs.reap_expired()
            for job in jobs.claim(worker_id, limit=10, lease_sec=120):
                try:
                    import json
                    payload = job.get("payload_json") or "{}"
                    body = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
                    handler = handlers.get(str(job.get("kind") or ""))
                    if handler is None:
                        logger.error("durable job has no handler: %s", job.get("kind"))
                        state = jobs.fail_or_retry(str(job["id"]), f"no handler for kind={job.get('kind')}")
                        self.metrics.incr("durable_jobs_dead" if state == "dead" else "durable_jobs_retry")
                        continue
                    handler(body)
                    jobs.complete(str(job["id"]))
                    self.metrics.incr("durable_jobs_done")
                except Exception as exc:
                    state = jobs.fail_or_retry(str(job["id"]), str(exc))
                    self.metrics.incr("durable_jobs_dead" if state == "dead" else "durable_jobs_retry")
                    logger.exception("durable job failed id=%s state=%s", job.get("id"), state)
        except Exception:
            logger.exception("durable job worker cycle failed")

    def _cycle_outbox(self) -> None:
        """Bridge durable outbox events to durable jobs; never blocks provider publishing."""
        outbox = self.comps.get("outbox")
        jobs = self.comps.get("durable_jobs")
        if not outbox or not jobs:
            return
        try:
            for event in outbox.claim(limit=50, lease_sec=60):
                try:
                    kind = str(event.get("event_type") or "event")
                    payload = event.get("payload_json") or "{}"
                    import json
                    body = json.loads(payload) if isinstance(payload, str) else (payload or {})
                    jobs.enqueue(
                        kind,
                        body,
                        provider=str(body.get("platform") or ""),
                        account_id=str(body.get("account_id") or ""),
                        job_id=f"outbox:{int(event["id"])}",
                    )
                    outbox.mark_published(int(event["id"]))
                except Exception as exc:
                    outbox.mark_failed(int(event["id"]), str(exc))
        except Exception:
            logger.debug("outbox cycle failed", exc_info=True)

    def _cycle_local_schedule_due(self) -> None:
        """N3: fire local_schedule / local-* holds when scheduled_for <= now."""
        from datetime import timezone
        clock = self.comps.get("clock")
        now = clock.now() if clock is not None else None
        if now is None:
            from datetime import datetime as _dt
            now = _dt.now(timezone.utc)
        if getattr(now, "tzinfo", None) is None:
            now = now.replace(tzinfo=timezone.utc)
        db = self.comps["db"]
        rows = db.fetchall(
            """
            SELECT entity_type, entity_id, platform, account_id, external_id, publish_mode, status,
                   scheduled_for AS scheduled_for
            FROM entity_platform_status
            WHERE status IN ('scheduled', 'ready')
              AND scheduled_for IS NOT NULL
              AND scheduled_for <= ?
              AND (
                    publish_mode = 'local_schedule'
                 OR external_id LIKE 'local-%'
              )
            LIMIT 50
            """,
            (now.isoformat(),),
        )
        pub = self.comps.get("publisher")
        recovery = self.comps.get("scheduler_recovery")
        if recovery is None:
            logger.error("local_schedule due skipped: scheduler recovery is required for lease-safe publishing")
            return
        try:
            recovery.recover_stale_leases()
            rows = recovery.claim_due_local(50)
        except Exception:
            logger.exception("scheduler recovery/claim failed; local_schedule cycle skipped")
            return
        if not pub or not rows:
            return
        for r in rows or []:
            et, eid, plat, aid = r["entity_type"], int(r["entity_id"]), r["platform"], str(r.get("account_id") or "")
            try:
                # Fire the exact content/media revision that was reserved for this slot.
                snapshot = db.fetchone(
                    "SELECT cr.content_json, cr.media_path, dt.revision_hash "
                    "FROM distribution_targets dt "
                    "JOIN content_revisions cr ON cr.revision_hash=dt.revision_hash "
                    "WHERE dt.entity_type=? AND dt.entity_id=? AND dt.platform=? AND dt.account_id=? "
                    "AND dt.scheduled_for=? ORDER BY dt.updated_at DESC LIMIT 1",
                    (et, eid, plat, aid, r.get("scheduled_for")),
                )
                if not snapshot:
                    logger.error("local_schedule snapshot missing %s/%s %s[%s]", et, eid, plat, aid)
                    db.execute(
                        "UPDATE entity_platform_status SET status='error', last_error=?, lease_until=NULL "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        ("local_schedule_snapshot_missing", et, eid, plat, aid),
                    )
                    continue
                import json as _json
                try:
                    content = _json.loads(snapshot.get("content_json") or "{}")
                except Exception as exc:
                    logger.error("local_schedule snapshot invalid %s/%s %s[%s]: %s", et, eid, plat, aid, exc)
                    db.execute(
                        "UPDATE entity_platform_status SET status='error', last_error=?, lease_until=NULL "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        ("local_schedule_snapshot_invalid", et, eid, plat, aid),
                    )
                    continue
                if not isinstance(content, dict):
                    logger.error("local_schedule snapshot is not an object %s/%s %s[%s]", et, eid, plat, aid)
                    db.execute(
                        "UPDATE entity_platform_status SET status='error', last_error=?, lease_until=NULL "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        ("local_schedule_snapshot_invalid", et, eid, plat, aid),
                    )
                    continue
                content.setdefault("content_kind", "video_native")
                media_path = snapshot.get("media_path") or None
                pub.publish(et, eid, plat, media_path, content, None, account_id=aid)
                # A real Publisher persists its own outcome. Lightweight/mock publishers used by
                # scheduler-only paths may not, so never leave a claimed lease dangling.
                try:
                    state = db.fetchone(
                        "SELECT status, external_id FROM entity_platform_status "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        (et, eid, plat, aid),
                    )
                    if state and state.get("status") in {"scheduled", "publishing"} and (
                        not state.get("external_id") or str(state.get("external_id")).startswith("local-")
                    ):
                        db.execute(
                            "UPDATE entity_platform_status SET status='ready', lease_until=NULL, external_id=NULL "
                            "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                            (et, eid, plat, aid),
                        )
                except Exception:
                    logger.debug("scheduler outcome reconciliation failed", exc_info=True)
            except Exception:
                logger.exception("local_schedule due failed %s %s %s", et, eid, plat)
                try:
                    db.execute(
                        "UPDATE entity_platform_status SET status='error', last_error=? "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        ("local_schedule_due_failed", et, eid, plat, aid),
                    )
                except Exception:
                    logger.exception("local_schedule error cleanup failed %s %s %s", et, eid, plat)

    def _cycle_ig_finalize(self) -> None:
        from datetime import datetime, timezone, timedelta
        try:
            from .platforms import default_registry
            from .auth_tokens import token_provider_for
            reg = self.comps.get("module_registry") or default_registry()
            if not reg.has("instagram"):
                return
        except Exception:
            logger.debug("ig finalize: module unavailable", exc_info=True)
            return
        now = self.comps["clock"].now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        window = now + timedelta(minutes=30)
        ig_account_id = str(getattr(self.cfg.platforms.get("instagram"), "account_id", "") or "")
        if not ig_account_id:
            accounts = self.comps["db"].fetchall(
                "SELECT DISTINCT account_id FROM entity_platform_status "
                "WHERE platform='instagram' AND account_id IS NOT NULL AND account_id!=''"
            )
            known_accounts = sorted({str(r.get("account_id") or "").strip() for r in accounts or [] if str(r.get("account_id") or "").strip()})
            if len(known_accounts) > 1:
                logger.warning("ig finalize skipped: account_id required for multiple accounts")
                return
            if len(known_accounts) == 1:
                ig_account_id = known_accounts[0]
        account_clause = ""
        query_params: tuple[Any, ...] = (
            window.isoformat(),
            (now - timedelta(minutes=5)).isoformat(),
            now.isoformat(),
        )
        if ig_account_id:
            account_clause = " AND account_id=?"
            query_params = query_params + (ig_account_id,)
        rows = self.comps["db"].fetchall(
            f"""
            SELECT entity_type, entity_id, account_id, external_id, external_sub_id, scheduled_for
            FROM entity_platform_status
            WHERE platform='instagram'
              AND status IN ('scheduled_platform', 'scheduled')
              AND COALESCE(external_sub_id, external_id) IS NOT NULL
              AND scheduled_for IS NOT NULL
              AND scheduled_for <= ? AND scheduled_for >= ?
              AND (next_retry_at IS NULL OR next_retry_at<=?)
              {account_clause}
            """,
            query_params,
        )
        modules: dict[str, Any] = {}
        for r in rows or []:
            cid = r.get("external_sub_id") or r.get("external_id")
            if not cid:
                continue
            account_id = str(r.get("account_id") or "")
            try:
                if account_id not in modules:
                    modules[account_id] = reg.create(
                        "instagram", dry_run=self.dry_run, cfg=self.cfg,
                        token_provider=token_provider_for("instagram"), account_id=account_id,
                        media_host=getattr(self.comps.get("media_transfer"), "media_host", None),
                    )
                mod = modules[account_id]
                if hasattr(mod, "finalize_container"):
                    mod.finalize_container(str(cid))
                elif hasattr(mod, "_api") and hasattr(mod._api, "publish_container"):
                    mid = mod._api.publish_container(str(cid))
                    pr_url = f"https://www.instagram.com/reel/{mid}/"
                    self.comps["db"].execute(
                        "UPDATE entity_platform_status SET status='published', external_id=?, external_url=?, published_at=? "
                        "WHERE entity_type=? AND entity_id=? AND platform='instagram' AND account_id=?",
                        (str(mid), pr_url, now.isoformat(), r["entity_type"], r["entity_id"], account_id),
                    )
                    logger.info("ig finalize: %s/%s/%s -> %s", r["entity_type"], r["entity_id"], account_id, mid)
            except Exception:
                logger.warning("ig finalize failed %s/%s/%s", r.get("entity_type"), r.get("entity_id"), account_id, exc_info=True)

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
            reg = self.comps.get("module_registry") or default_registry()
            if reg is not None and reg.has(resolved.module_id):
                broker = self.comps.get("broker")
                pcfg = self.cfg.platforms.get("youtube")
                iid = getattr(pcfg, "account_id", "") or "" if pcfg else ""

                from .auth_tokens import token_provider_for
                _shared_tp = token_provider_for("youtube")

                def _tp(p: str = "youtube", b=broker, i: str = iid) -> str:
                    if b is not None:
                        try:
                            tok = str((b.get(p, i) or {}).get("token") or "")
                            if tok:
                                return tok
                        except Exception:
                            logger.debug("claims token broker read failed", exc_info=True)
                    return _shared_tp(p, i)

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
            SELECT eps.entity_type, eps.entity_id,
                   eps.external_id AS external_id,
                   eps.scheduled_for AS scheduled_for,
                   eps.status
            FROM entity_platform_status eps
            WHERE eps.platform='youtube'
              AND eps.status IN ('ready', 'scheduled', 'scheduled_platform')
              AND eps.scheduled_for IS NOT NULL
            """
        )
        items: list = []
        for r in rows:
            sched = r["scheduled_for"]
            try:
                dt = datetime.fromisoformat(str(sched))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                local_d = dt.astimezone(tz).date().isoformat()
            except Exception:
                continue
            if local_d not in horizon_set:
                continue
            if r["external_id"]:
                items.append(AheadItem(path="", title="", slot=dt, external_id=str(r["external_id"])))
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

