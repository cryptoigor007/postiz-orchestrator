

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


def _now_iso():
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()
