"""P1.6: smoke-тесты миграций схемы (fresh → v13, старые версии, идемпотентность)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.db import SCHEMA_VERSION, Database  # noqa: E402


def _cols(db: Database, table: str) -> set[str]:
    return {r["name"] for r in db.fetchall(f"PRAGMA table_info({table})")}


def test_fresh_db_schema_version_and_columns(tmp_path):
    db = Database(tmp_path / "fresh.sqlite")
    ver = db.fetchone("SELECT value FROM system_state WHERE key='schema_version'")["value"]
    assert int(ver) == SCHEMA_VERSION
    cols = _cols(db, "platform_queue_state")
    assert {"pending_series_end_question", "pending_series_end_at",
            "pending_backlog_question", "pending_backlog_at"} <= cols
    assert {"legacy_post_id", "release_url"} <= _cols(db, "entity_platform_status")


def test_migration_from_v11_adds_v12_index_and_v13_columns(tmp_path):
    db = Database(tmp_path / "old.sqlite")
    db.execute("UPDATE system_state SET value='11' WHERE key='schema_version'")
    db2 = Database(tmp_path / "old.sqlite")  # повторное открытие → миграция
    ver = db2.fetchone("SELECT value FROM system_state WHERE key='schema_version'")["value"]
    assert int(ver) == SCHEMA_VERSION
    idx = db2.fetchall("SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                       ("idx_eps_platform_id_unique",))
    assert idx, "v12 unique-индекс должен быть создан"
    assert {"pending_backlog_question", "pending_backlog_at"} <= _cols(db2, "platform_queue_state")


def test_migration_idempotent(tmp_path):
    db = Database(tmp_path / "idem.sqlite")
    for _ in range(3):
        Database(tmp_path / "idem.sqlite")  # повторные открытия не ломают
    ver = db.fetchone("SELECT value FROM system_state WHERE key='schema_version'")["value"]
    assert int(ver) == SCHEMA_VERSION


def test_migration_duplicate_pids_graceful(tmp_path):
    """Дубли legacy_post_id не должны ломать миграцию v12 (индекс не создаётся, но и не падаем)."""
    db = Database(tmp_path / "dup.sqlite")
    db.execute("DROP INDEX IF EXISTS idx_eps_platform_id_unique")  # легаси-БД без индекса
    now = "2026-01-01T00:00:00+00:00"
    db.execute("INSERT INTO shorts (source, folder_path, title_text, created_at) "
               "VALUES ('x','/s','t',?)", (now,))
    db.execute("INSERT INTO shorts (source, folder_path, title_text, created_at) "
               "VALUES ('x','/s2','t2',?)", (now,))
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
               "legacy_post_id) VALUES ('short', 1, 'youtube', 'scheduled', 'dup1')")
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
               "legacy_post_id) VALUES ('short', 2, 'youtube', 'scheduled', 'dup1')")
    db.execute("DROP INDEX IF EXISTS idx_eps_platform_id_unique")
    db.execute("UPDATE system_state SET value='11' WHERE key='schema_version'")
    db2 = Database(tmp_path / "dup.sqlite")  # миграция не должна падать
    assert int(db2.fetchone("SELECT value FROM system_state WHERE key='schema_version'")["value"]) == SCHEMA_VERSION


def test_current_schema_restore_drill_from_backup_copy(tmp_path):
    from shutil import copy2
    from orchestrator.backup import run_backup
    from orchestrator.config import load_config
    from orchestrator.db import Database, SCHEMA_VERSION

    src = tmp_path / "live.sqlite"
    db = Database(src)
    db.execute("INSERT INTO long_videos(source,folder_path,title_text,created_at) VALUES('s','/restore','restore-check','now')")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.ci.yaml")
    backup = run_backup(db, cfg, tmp_path / "backups")
    restored = tmp_path / "restored.sqlite"
    copy2(backup, restored)
    db2 = Database(restored)
    assert SCHEMA_VERSION == 28
    assert int(db2.get_setting("schema_version")) == SCHEMA_VERSION
    assert db2.fetchone("SELECT title_text FROM long_videos WHERE title_text='restore-check'") is not None
    assert db2.fetchone("PRAGMA integrity_check")["integrity_check"] == "ok"
    assert db2.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='platform_safety_account_state'") is not None
    assert db2.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='platform_queue_account_state'") is not None
    assert db2.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='webapp_rate_limits'") is not None
