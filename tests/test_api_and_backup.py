

def test_backup_prunes_old_publish_log(tmp_path):
    """Бэкап попутно чистит publish_log старше 90 дней (журнал не растёт вечно)."""
    from pathlib import Path

    from orchestrator.backup import run_backup
    from orchestrator.config import load_config
    from orchestrator.db import Database

    db = Database(tmp_path / "b.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db.execute(
        "INSERT INTO publish_log (entity_type, entity_id, platform, action, details, created_at) "
        "VALUES ('short', 1, 'youtube', 'created', 'x', '2020-01-01T00:00:00+00:00')")
    db.execute(
        "INSERT INTO publish_log (entity_type, entity_id, platform, action, details, created_at) "
        "VALUES ('short', 2, 'youtube', 'created', 'y', ?)", (_now_iso(),))
    run_backup(db, cfg, tmp_path / "bk")
    left = db.fetchall("SELECT entity_id FROM publish_log")
    assert [r["entity_id"] for r in left] == [2]


def test_backup_cleanup_covers_named_snapshots(tmp_path):
    """Ретенция чистит и «именованные» снимки, а не только data_*.sqlite.

    Раньше data.sqlite.before_rename, data-before-cleanup-*, pre_migration_* копились вечно.
    Живая БД data.sqlite и свежие снимки должны оставаться на месте.
    """
    import os
    import time

    from orchestrator.backup import _cleanup

    old = time.time() - 20 * 86400
    fresh = time.time()
    aged = [
        "data_20260101_000000.sqlite",
        "data.sqlite.before_rename",
        "data.sqlite.before-rename-1789922526",
        "data.sqlite.before_junkfix",
        "data-before-cleanup-20260923-024732.sqlite",
        "data-before-base-cleanup-20260923-001305.sqlite",
        "pre_migration_v13_to_v14_20260921T192341.817650+0000.sqlite",
    ]
    kept = [
        "data_20260923_000000.sqlite",
        "data.sqlite.before-rename-1790000000",
        "pre_migration_v14_to_v15_x.sqlite",
        "data.sqlite",  # живая БД — не удаляем никогда
        "metrics.json",
    ]
    for name in aged + kept:
        p = tmp_path / name
        p.write_text("x")
        stamp = old if name in aged else fresh
        os.utime(p, (stamp, stamp))

    _cleanup(tmp_path, 14)

    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(kept)


def _now_iso():
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()
