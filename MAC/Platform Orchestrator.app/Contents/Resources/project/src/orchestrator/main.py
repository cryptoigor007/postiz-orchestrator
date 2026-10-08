from __future__ import annotations

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError as exc:
    logging.getLogger("orchestrator").debug("python-dotenv unavailable: %s", type(exc).__name__)
import argparse
import json
import logging
import os
import sys
from pathlib import Path

from . import __version__
from .backlog import BacklogManager
from .backup import run_backup
from .clock import SystemClock
from .config import load_config
from .db import Database
from .engines.token_broker_client import TokenBrokerClient
from .jobs import JobRegistry
from .link_updater import LinkUpdater
from .manual_sources import build_manual_sources
from .manual_uploads import ManualUploadsService
from .overflow import move_excess_shorts
# R2/R8: no platform client on default path
from .publisher import Publisher
from .safety import SafetyChecker
from .schedule_guard import ScheduleGuard, eps_source
from .scheduler import Scheduler
from .status_sync import StatusSync
from .reconciliation import ModuleReconciliation
from .tail import TailManager
from .telegram_bot import TelegramNotifier, setup_commands
from .telegram_publish import create_telegram_publisher
from .telegram_transport import TelegramTransport
from .watcher import Watcher
from .pidfile import acquire_pidfile, pidfile_path_from_env

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# SEC: httpx на INFO печатает полные URL, включая https://api.telegram.org/bot<TOKEN>/...
# и platform-запросы — приглушаем транспортные логгеры до WARNING.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("orchestrator")


def _ensure_single_instance(args: argparse.Namespace) -> None:
    """Z01/REL-02: refuse second process on same pidfile."""
    if getattr(args, "no_pidfile", False):
        return
    path = getattr(args, "pidfile", None) or pidfile_path_from_env()
    acquire_pidfile(path)


def build(args: argparse.Namespace) -> dict:
    cfg = load_config(args.config)
    db = Database(args.db)
    platforms = list(cfg.platforms.keys())
    db.ensure_platform_states(platforms)

    clock = SystemClock()
    # HARD_CUT: provider modules are the production publish path. Legacy engine
    # wiring is opt-in for migration-only/manual compatibility and never default.
    platform = None  # removed in C13/R8
    tg_pub = create_telegram_publisher(cfg)
    if tg_pub is not None:
        logger.info("Telegram: публикация через Bot API, канал %s",
                    getattr(cfg.platforms.get("telegram"), "publish_chat_id", "?"))
    safety = SafetyChecker(db, cfg, clock)
    try:
        _guard_ttl = int(os.getenv("ORCH_GUARD_TTL_SEC", "") or 120)
    except ValueError:
        _guard_ttl = 120
    guard = ScheduleGuard(cfg, clock, ttl_sec=_guard_ttl,
                          sources=[("eps", eps_source(db))])
    comps_guard = guard
    broker = None
    if os.getenv("TOKEN_BROKER_URL"):
        broker = TokenBrokerClient(os.environ["TOKEN_BROKER_URL"],
                                   os.getenv("TOKEN_BROKER_SECRET", ""))
    from .provider_supervisor import ProviderSupervisor
    from .provider_access import ProviderAccessStore
    from .outbox import Outbox, DurableJobStore
    from .consistency import ConsistencySweeper
    supervisor = ProviderSupervisor(db)
    provider_access = ProviderAccessStore(db)
    outbox = Outbox(db)
    from .media_transfer import MediaTransferManager
    media_transfer = MediaTransferManager(db)
    from .token_lifecycle import TokenLifecycleStore
    from .webhook_processor import WebhookEventProcessor
    from .scheduler_recovery import SchedulerRecovery
    token_lifecycle = TokenLifecycleStore(os.getenv("TOKENS_DIR", "tokens"), db=db)
    webhook_processor = WebhookEventProcessor(db)
    scheduler_recovery = SchedulerRecovery(db, clock)
    durable_jobs = DurableJobStore(db)
    # publish.completed is deliberately an audit channel: the publish transaction
    # already committed EPS state. Re-running status_sync/notifications here could
    # duplicate provider side effects, so this durable handler records only audit+metrics.
    PUBLISH_COMPLETED_SIDE_EFFECTS = ("audit_log", "metrics")
    def _job_publish_completed(body):
        platform = str(body.get("platform") or "")
        entity_type = str(body.get("entity_type") or "")
        entity_id = int(body.get("entity_id") or 0)
        external_id = str(body.get("external_id") or "")
        status = str(body.get("status") or "")
        logger.info("durable event publish.completed: %s/%s/%s", platform, entity_type, entity_id)
        if entity_type and entity_id:
            db.log(entity_type, entity_id, platform or None, "publish.completed", external_id)
        metrics.incr("publish_completed_events")
        if status in {"published", "scheduled", "scheduled_platform", "uploaded_inbox"}:
            metrics.incr(f"publish_completed_status_{status}")
    job_handlers = {"publish.completed": _job_publish_completed}
    # module_registry attached after init below
    publisher = Publisher(db, cfg, safety, clock, dry_run=args.dry_run,
                          guard=guard, broker=broker, supervisor=supervisor, outbox=outbox)
    scheduler = Scheduler(db, cfg, publisher, safety, clock, telegram=tg_pub)
    status_sync = StatusSync(db, clock, cfg)  # module-only (F2)
    recon = ModuleReconciliation(db, cfg, clock)  # F19 module recon
    watcher = Watcher(db, cfg, clock, args.watch_roots or [],
                     max_age_days=int(getattr(cfg, "watch_max_age_days", 3650) or 0))
    tg = TelegramNotifier(cfg, db, clock)
    tail = TailManager(db, cfg, clock, tg)
    link_upd = LinkUpdater(db, cfg, clock, tg)
    manual = ManualUploadsService(db, cfg, clock)
    try:
        manual_sources = build_manual_sources(cfg, os.environ)
    except Exception:
        manual_sources = {}
    backlog = BacklogManager(db, cfg, clock, scheduler=scheduler, notifier=tg)

    # Module registry + B2 media host for runner cycles (claims/scan/daily_ahead/TTL)
    try:
        from .platforms import default_registry
        module_registry = default_registry()
    except Exception:
        module_registry = None
        logger.warning("module registry unavailable", exc_info=True)
    try:
        from .media_host.b2 import create_media_host
        import os as _os
        media_host = create_media_host(
            dry_run=bool(args.dry_run),
            db=db,
            key_id=_os.getenv("B2_KEY_ID", ""),
            app_key=_os.getenv("B2_APPLICATION_KEY", ""),
            bucket_id=_os.getenv("B2_BUCKET_ID", ""),
            bucket_name=_os.getenv("B2_BUCKET", ""),
        )
    except Exception:
        media_host = None
        logger.debug("media_host init skipped", exc_info=True)

    from .publish_recovery import PublishAttemptRecovery
    publish_recovery = PublishAttemptRecovery(db, module_registry, cfg=cfg, clock=clock) if module_registry is not None else None

    def _consistency_factory(platform: str, **deps):
        if module_registry is None:
            raise RuntimeError("module registry unavailable")
        from .auth_tokens import token_provider_for
        return module_registry.create(
            platform, cfg=cfg, dry_run=bool(args.dry_run),
            token_provider=token_provider_for(platform),
            account_id=str(deps.get("account_id") or ""),
            media_host=media_host,
        )

    consistency = ConsistencySweeper(
        db, module_registry, cfg, module_factory=_consistency_factory
    ) if module_registry is not None else None

    comps = {
        "cfg": cfg,
        "db": db,
        "jobs": JobRegistry(),
        "guard": comps_guard,
        "clock": clock,
        "safety": safety,
        "publisher": publisher,
        "scheduler": scheduler,
        "status_sync": status_sync,
        "recon": recon,
        "watcher": watcher,
        "tg": tg,
        "tail": tail,
        "link_upd": link_upd,
        "manual": manual,
        "manual_sources": manual_sources,
        "backlog": backlog,
        "broker": broker,
        "module_registry": module_registry,
        "media_host": media_host,
        "provider_supervisor": supervisor,
        "provider_access": provider_access,
        "outbox": outbox,
        "durable_jobs": durable_jobs,
        "media_transfer": media_transfer,
        "token_lifecycle": token_lifecycle,
        "webhook_processor": webhook_processor,
        "scheduler_recovery": scheduler_recovery,
        "job_handlers": job_handlers,
        "publish_recovery": publish_recovery,
        "consistency": consistency,
    }
    if module_registry is not None and hasattr(publisher, '_module_registry'):
        publisher._module_registry = module_registry
    if media_host is not None and hasattr(publisher, 'media_host'):
        publisher.media_host = media_host
    if hasattr(recon, "media_host"):
        recon.media_host = media_host
    setup_commands(tg, comps)
    db = comps["db"]
    transport = TelegramTransport(
        on_message=tg.handle_update,
        load_seen=lambda: int(db.get_setting("tg_seen_update_id") or 0),
        save_seen=lambda v: db.set_setting("tg_seen_update_id", str(v)),
    )
    tg.transport = transport
    comps["tg_transport"] = transport
    transport.recover_voices()  # голосовые без расшифровки — добрать после перезапуска
    return comps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=f"Content publish orchestrator v{__version__}"
    )
    parser.add_argument("--pidfile", default="", help="single-instance pidfile path")
    parser.add_argument("--no-pidfile", action="store_true", help="disable pidfile lock")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--db", default="data/data.sqlite")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--watch-roots", nargs="*", default=[])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--schedule", action="store_true")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--reconcile", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--test-schedule", action="store_true",
                        help="Пробный пост: --test-platform P --test-entity TYPE:ID [--test-delay N] [--test-dry-run]")
    parser.add_argument("--test-platform", default="")
    parser.add_argument("--test-entity", default="", help="short:123 | long_video:45")
    parser.add_argument("--test-delay", type=int, default=None)
    parser.add_argument("--test-dry-run", action="store_true")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--daemon", action="store_true", help="Run continuous loop")
    parser.add_argument("--remote-scan", action="store_true", help="Run remote inventory scan")
    parser.add_argument("--claims", action="store_true", help="Run YouTube claims checkpoint")
    parser.add_argument("--b2-cleanup", action="store_true", help="Run B2 TTL cleanup")
    parser.add_argument("--health-port", type=int, default=8080)
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.read_only:
        # P1-2: раньше флаг только логировался, а защита читает env/атрибут cfg.
        # Без этого `--read-only --daemon` продолжал публиковать «вживую».
        os.environ["ORCH_READ_ONLY"] = "1"
        logger.info("Read-only mode (ORCH_READ_ONLY=1)")

    _ensure_single_instance(args)
    comps = build(args)
    cfg = comps["cfg"]


    # A5: тест-контур включён, но боевые integration_id не помечены — предупреждаем явно
    _tp = getattr(cfg, "test_publish", None)
    if _tp is not None and getattr(_tp, "enabled", False) and not (getattr(_tp, "prod_integration_ids", None) or []):
        logging.getLogger(__name__).warning(
            "test_publish.enabled=true, но prod_integration_ids пуст: тест разрешён только для "
            "test_integration_ids=%s (fail-closed). При переходе на боевые каналы — заполните prod ids.",
            list(getattr(_tp, "test_integration_ids", []) or []),
        )

    from .metrics import Metrics as _Metrics

    metrics = comps.get("metrics") or _Metrics(Path(args.db).resolve().parent / "metrics.json")
    comps["metrics"] = metrics

    if args.daemon:
        from .runner import Runner
        comps["tg_transport"].start()
        try:
            Runner(comps, dry_run=args.dry_run, health_port=args.health_port).run_forever()
        finally:
            comps["tg_transport"].stop()
        return 0

    if args.scan or args.once:
        stats = comps["watcher"].scan()
        logger.info("Scan: %s", stats)
        parents = comps["db"].fetchall(
            "SELECT DISTINCT parent_video_id FROM shorts WHERE parent_video_id IS NOT NULL"
        )
        for p in parents:
            move_excess_shorts(comps["db"], cfg, comps["clock"], p["parent_video_id"])

    if args.schedule or args.once:
        _roots = [str(r) for r in comps["watcher"].effective_roots()]
        n = comps["scheduler"].schedule_long_videos(scope_roots=_roots)
        logger.info("Scheduled long: %s", n)
        n2 = comps["scheduler"].schedule_standalone_shorts(
            comps["tail"], scope_roots=_roots)
        logger.info("Scheduled standalone: %s", n2)
        pubs = comps["db"].fetchall(
            "SELECT entity_id, platform FROM entity_platform_status "
            "WHERE entity_type='long_video' AND status IN ('published','scheduled')"
        )
        for r in pubs:
            nt = comps["scheduler"].schedule_thematic_shorts(
                r["entity_id"], r["platform"], scope_roots=_roots)
            if nt:
                logger.info("Thematic %s/%s: %s", r["entity_id"], r["platform"], nt)

    if args.sync or args.once:
        n = comps["status_sync"].sync()
        logger.info("Status sync: %s", n)
        comps["link_upd"].check_missing_urls()
        for p in cfg.platforms:
            comps["tail"].check_soft_enter(p)

    if args.reconcile or args.once:
        r = comps["recon"].run()
        logger.info("Reconciliation: %s", r)

    if args.test_schedule:
        from .test_publish import TestPublishError, schedule_test_post

        if ":" not in args.test_entity or not args.test_platform:
            print("нужно: --test-platform P --test-entity TYPE:ID", file=sys.stderr)
            return 2
        etype, eid = args.test_entity.split(":", 1)
        try:
            res = schedule_test_post(comps, platform=args.test_platform,
                                     entity_type=etype.strip(), entity_id=int(eid),
                                     delay_minutes=args.test_delay,
                                     dry_run=args.test_dry_run)
        except TestPublishError as e:
            print(f"test-schedule: {e}", file=sys.stderr)
            return 1
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.remote_scan:
        try:
            from .remote_scan.service import RemoteScanService
            from .platforms import default_registry
            svc = RemoteScanService(
                comps["db"], cfg, module_registry=default_registry(),
                media_host=comps.get("media_host"),
            )
            out = []
            for plat, pcfg in cfg.platforms.items():
                if getattr(pcfg, "enabled", False):
                    out.append(svc.scan_platform(plat))
            print(out)
        except Exception as e:
            logger.exception("remote-scan failed")
            print(f"remote-scan error: {e}", file=sys.stderr)
            return 1
        return 0

    if args.claims:
        try:
            from .claims import run_claims_check
            from .platforms import default_registry, resolve_engine
            from .auth_tokens import token_provider_for
            yt = None
            eng = str(cfg.engine_for("youtube") or "")
            try:
                resolved = resolve_engine(eng)
                reg = comps.get("module_registry") or default_registry()
                if resolved.kind == "module" and resolved.module_id and reg.has(resolved.module_id):
                    yt = reg.create(
                        resolved.module_id, cfg=cfg, dry_run=bool(args.dry_run),
                        http=None, token_provider=token_provider_for("youtube"),
                        media_host=comps.get("media_host"),
                        account_id=str(getattr(getattr(cfg, "platforms", {}).get("youtube"), "account_id", "") or ""),
                    )
            except Exception:
                logger.debug("youtube module create for CLI claims failed", exc_info=True)
            res = run_claims_check(
                comps["db"], clock=comps.get("clock"),
                youtube_module=yt, notifier=comps.get("tg"),
                account_id=str(getattr(getattr(cfg, "platforms", {}).get("youtube"), "account_id", "") or ""),
            )
            print(res)
        except Exception as e:
            logger.exception("claims failed")
            print(f"claims error: {e}", file=sys.stderr)
            return 1
        return 0

    if args.b2_cleanup:
        try:
            from .media_host.b2 import create_media_host
            host = create_media_host(dry_run=args.dry_run, db=comps["db"])
            n = host.cleanup_expired()
            print({"deleted": n})
        except Exception as e:
            logger.exception("b2-cleanup failed")
            print(f"b2-cleanup error: {e}", file=sys.stderr)
            return 1
        return 0

    if args.backup or args.once:
        bdir = Path(args.db).resolve().parent.parent / "backups"
        try:
            path = run_backup(comps["db"], cfg, bdir)
        except Exception:
            logger.exception("backup failed (не критично, продолжаем)")
            path = None
        logger.info("Backup: %s", path)

    if not any([args.scan, args.schedule, args.sync, args.reconcile, args.backup, args.once]):
        logger.info("Orchestrator v%s ready (dry-run=%s)", __version__, args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
