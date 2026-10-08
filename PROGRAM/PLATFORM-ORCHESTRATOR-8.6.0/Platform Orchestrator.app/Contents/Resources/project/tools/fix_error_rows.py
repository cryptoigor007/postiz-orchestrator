#!/usr/bin/env python3
"""Разовая починка строк после инцидента с обложкой (module-path StatusSync/delete).

HARD_CUT: module StatusSync only; no Postiz / HttpPlatform client required.
"""
from __future__ import annotations
import argparse, sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from orchestrator.clock import SystemClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.status_sync import StatusSync
from orchestrator.telegram_publish import is_bot_post_id

WARN_PREFIX = "Опубликовано без обложки"

def short_reason(msg: Any, limit: int = 300) -> str:
    return (str(msg) if msg else "")[:limit]

def _ids(raw: str) -> list[int]:
    out = []
    for part in str(raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part:
            out.append(int(part))
    return out

def _snapshot(db: Database, ids: list[int] | None) -> dict[tuple, dict]:
    sql = ("SELECT entity_type, entity_id, platform, status, release_url, last_error, "
           "legacy_post_id, legacy_scheduled_for, link_updated_at "
           "FROM entity_platform_status WHERE platform IN ('youtube','telegram')")
    rows = db.fetchall(sql)
    out = {}
    for r in rows:
        key = (r["entity_type"], r["entity_id"], r["platform"])
        if ids and r["entity_id"] not in ids:
            continue
        out[key] = dict(r)
    return out

def _show_diff(before, after):
    changed = False
    for k in sorted(set(before) | set(after)):
        if before.get(k) != after.get(k):
            changed = True
            print(f"  {k}: {before.get(k)} → {after.get(k)}")
    return changed

def apply_links(db: Database, links: dict[int, str], commit: bool) -> None:
    for sid, url in links.items():
        row = db.fetchone(
            "SELECT status, release_url, last_error FROM entity_platform_status "
            "WHERE entity_type='short' AND entity_id=? AND platform='youtube'", (sid,))
        if row is None:
            print(f"  short {sid} [youtube]: строки нет — пропускаю"); continue
        if row["status"] == "published" and row["release_url"] == url:
            print(f"  short {sid} [youtube]: уже published — ок"); continue
        note = str(row["last_error"] or "")
        if not note.startswith(WARN_PREFIX):
            note = f"{WARN_PREFIX}: видео на канале, обложку поставить не удалось, ссылка восстановлена вручную"
        print(f"  short {sid} [youtube]: {row['status']!r} → 'published', release_url={url!r}")
        if not commit: continue
        db.execute(
            "UPDATE entity_platform_status SET status='published', release_url=?, "
            "last_error=?, published_at=COALESCE(published_at, ?) "
            "WHERE entity_type='short' AND entity_id=? AND platform='youtube'",
            (url, short_reason(note, 300), datetime.now(UTC).isoformat(), sid))
        db.log("short", sid, "youtube", "release_url_restored", url)

def requeue_telegram(db: Database, platform: Any, sid: int, commit: bool) -> None:
    row = db.fetchone(
        "SELECT * FROM entity_platform_status WHERE entity_type='short' AND entity_id=? "
        "AND platform='telegram'", (sid,))
    if row is None:
        print(f"  short {sid} [telegram]: строки нет"); return
    if row["status"] == "published" and (row.get("legacy_post_id") or row.get("external_id")):
        print(f"  short {sid} [telegram]: уже опубликован — не трогаем"); return
    print(f"  short {sid} [telegram]: {row['status']!r} → 'ready'")
    old_id = row.get("external_id") or row.get("legacy_post_id")
    if old_id and not is_bot_post_id(str(old_id)):
        if not commit:
            print(f"      (dry-run: при --commit удалим {old_id})")
        else:
            try:
                if platform is not None and hasattr(platform, "delete_post"):
                    platform.delete_post(str(old_id))
                elif platform is not None and hasattr(platform, "delete"):
                    platform.delete(str(old_id))
                print(f"      удалён {old_id}")
            except Exception as e:
                print(f"      не удалось удалить {old_id}: {e}")
    if commit:
        db.execute(
            "UPDATE entity_platform_status SET status='ready', last_error='waiting_for_youtube', "
            "legacy_post_id=NULL, external_id=NULL, link_updated_at=NULL, published_at=NULL "
            "WHERE entity_type='short' AND entity_id=? AND platform='telegram'", (sid,))
        db.log("short", sid, "telegram", "requeued_after_fix", "link-режим")

def _copy_db(src: str) -> str:
    import sqlite3, tempfile
    dst = tempfile.mktemp(suffix=".sqlite")
    origin = sqlite3.connect(src)
    try:
        backup = sqlite3.connect(dst)
        try: origin.backup(backup)
        finally: backup.close()
    finally: origin.close()
    return str(dst)

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="data/data.sqlite")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--youtube", default="399,400")
    ap.add_argument("--telegram", default="270,399,400")
    ap.add_argument("--link", action="append", default=[], metavar="ID=URL")
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.commit:
        db_path, mode = args.db, f"ЗАПИСЬ в {args.db}"
    else:
        db_path = _copy_db(args.db)
        mode = f"dry-run на копии {args.db}"
    db = Database(db_path)
    clock = SystemClock()
    print(f"БД: {db_path}   режим: {mode}")
    yt_ids = _ids(args.youtube); tg_ids = _ids(args.telegram)
    links = {}
    for item in args.link:
        sid_raw, _, url = str(item).partition("=")
        if sid_raw.strip().isdigit() and url.strip().startswith("http"):
            links[int(sid_raw.strip())] = url.strip()
    scope = yt_ids + tg_ids + list(links)
    before = _snapshot(db, scope)
    print("\n1) StatusSync module-path")
    from orchestrator.platforms import default_registry
    sync = StatusSync(db, clock, cfg, registry=default_registry())
    try:
        print(f"  StatusSync: {sync.sync()}")
    except Exception as e:
        print(f"  StatusSync fail: {e}")
    if links:
        print("\n2) apply_links"); apply_links(db, links, args.commit)
    print("\n3) requeue telegram")
    for sid in tg_ids:
        requeue_telegram(db, None, sid, args.commit)
    after = _snapshot(db, scope)
    if not _show_diff(before, after): print("  нет")
    if not args.commit:
        print(f"\nDry-run ({db_path}). Для записи — --commit.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
