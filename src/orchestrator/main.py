from __future__ import annotations

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import argparse
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
from .link_updater import LinkUpdater
from .manual_sources import build_manual_sources
from .manual_uploads import ManualUploadsService
from .overflow import move_excess_shorts
from .postiz_factory import create_postiz_client
from .publisher import Publisher
from .safety import SafetyChecker
from .schedule_guard import ScheduleGuard, n8n_source, postiz_source
from .scheduler import Scheduler
from .status_sync import Reconciliation, StatusSync
from .tail import TailManager
from .telegram_bot import TelegramNotifier, setup_commands
from .telegram_transport import TelegramTransport
from .watcher import Watcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("orchestrator")


def build(args: argparse.Namespace) -> dict:
    cfg = load_config(args.config)
    db = Database(args.db)
    platforms = list(cfg.platforms.keys())
    db.ensure_platform_states(platforms)

    clock = SystemClock()
    postiz = create_postiz_client(dry_run=args.dry_run)
    safety = SafetyChecker(db, cfg, clock)
    guard = ScheduleGuard(cfg, clock, sources=[("postiz", postiz_source(postiz))])
    publisher = Publisher(db, cfg, postiz, safety, clock, dry_run=args.dry_run, guard=guard)
    scheduler = Scheduler(db, cfg, publisher, safety, clock)
    status_sync = StatusSync(db, postiz, clock, cfg)
    recon = Reconciliation(db, postiz, clock)
    watcher = Watcher(db, cfg, clock, args.watch_roots or [])
    tg = TelegramNotifier(cfg, db, clock)
    tail = TailManager(db, cfg, clock, tg)
    link_upd = LinkUpdater(db, cfg, postiz, clock, tg)
    manual = ManualUploadsService(db, cfg, clock)
    manual_sources = build_manual_sources(cfg, postiz, os.environ)
    try:
        from .engines.n8n_engine import N8nEngine
        for _p, _eng in manual_sources.items():
            if isinstance(_eng, N8nEngine):
                guard.sources.append((f"n8n:{_p}", n8n_source(_eng)))
    except Exception:
        pass
    backlog = BacklogManager(db, cfg, clock, scheduler=scheduler, notifier=tg)

    comps = {
        "cfg": cfg,
        "db": db,
        "clock": clock,
        "postiz": postiz,
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
    }
    setup_commands(tg, comps)
    db = comps["db"]
    transport = TelegramTransport(
        on_message=tg.handle_update,
        load_seen=lambda: int(db.get_setting("tg_seen_update_id") or 0),
        save_seen=lambda v: db.set_setting("tg_seen_update_id", str(v)),
    )
    tg.transport = transport
    comps["tg_transport"] = transport
    return comps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=f"Content publish orchestrator v{__version__}"
    )
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
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--daemon", action="store_true", help="Run continuous loop")
    parser.add_argument("--health-port", type=int, default=8080)
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.read_only:
        logger.info("Read-only mode")

    comps = build(args)
    cfg = comps["cfg"]


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
        n = comps["scheduler"].schedule_long_videos()
        logger.info("Scheduled long: %s", n)
        n2 = comps["scheduler"].schedule_standalone_shorts(comps["tail"])
        logger.info("Scheduled standalone: %s", n2)
        pubs = comps["db"].fetchall(
            "SELECT entity_id, platform FROM entity_platform_status "
            "WHERE entity_type='long_video' AND status='published'"
        )
        for r in pubs:
            nt = comps["scheduler"].schedule_thematic_shorts(r["entity_id"], r["platform"])
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

    if args.backup or args.once:
        bdir = Path(args.db).resolve().parent.parent / "backups"
        path = run_backup(comps["db"], cfg, bdir)
        logger.info("Backup: %s", path)

    if not any([args.scan, args.schedule, args.sync, args.reconcile, args.backup, args.once]):
        logger.info("Orchestrator v%s ready (dry-run=%s)", __version__, args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
