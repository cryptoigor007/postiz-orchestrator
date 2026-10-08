#!/usr/bin/env python3
"""YT-01 orphan-reaper: videos.list vs EPS after lease expiry / failed publishing.

Usage:
  PYTHONPATH=src python tools/yt_orphan_reaper.py --db data/orch.sqlite --dry-run
  PYTHONPATH=src python tools/yt_orphan_reaper.py --db data/orch.sqlite --apply
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Callable

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("yt_orphan_reaper")


def reaper_diff(
    eps_external_ids: set[str],
    remote_ids: set[str],
) -> tuple[set[str], set[str]]:
    """Return (missing_on_platform, remote_orphans)."""
    missing = set(eps_external_ids) - set(remote_ids)
    orphans = set(remote_ids) - set(eps_external_ids)
    return missing, orphans


def run(
    db_path: str,
    *,
    apply: bool = False,
    list_remote: Callable[[], list[str]] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"eps": 0, "remote": 0, "missing": [], "orphans": [], "applied": 0}
    if list_remote is None:
        list_remote = lambda: []  # noqa: E731 — live list requires YT module token

    eps_ids: set[str] = set()
    try:
        from orchestrator.db import Database
        db = Database(db_path)
        rows = db.fetchall(
            "SELECT entity_type, entity_id, external_id, status FROM entity_platform_status "
            "WHERE platform='youtube' AND external_id IS NOT NULL AND external_id != '' "
            "AND status IN ('published','scheduled','publishing','scheduled_platform')"
        )
        out["eps"] = len(rows)
        for r in rows:
            eps_ids.add(str(r["external_id"]))
    except Exception as e:
        log.warning("db: %s", e)
        return out

    try:
        remote = set(str(x) for x in (list_remote() or []) if x)
    except Exception as e:
        log.warning("list_remote: %s", e)
        remote = set()
    out["remote"] = len(remote)
    missing, orphans = reaper_diff(eps_ids, remote)
    out["missing"] = sorted(missing)
    out["orphans"] = sorted(orphans)
    log.info(
        "eps=%s remote=%s missing_on_platform=%s remote_orphans=%s",
        out["eps"], out["remote"], len(missing), len(orphans),
    )
    if apply and missing:
        try:
            from orchestrator.db import Database
            db = Database(db_path)
            for eid in missing:
                db.execute(
                    "UPDATE entity_platform_status SET last_error=? "
                    "WHERE platform='youtube' AND external_id=?",
                    (f"missing_on_platform:1", eid),
                )
                out["applied"] += 1
        except Exception as e:
            log.warning("apply: %s", e)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="YouTube orphan reaper vs EPS")
    ap.add_argument("--db", default="data/orchestrator.sqlite")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not Path(args.db).exists():
        log.warning("db not found — nothing to do")
        return 0
    run(args.db, apply=bool(args.apply))
    return 0


if __name__ == "__main__":
    sys.exit(main())
