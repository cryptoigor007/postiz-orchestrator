
"""F4: schema 18 — platform_* backfill to external_*; media_host_objects; no required platform writes."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.db import Database, SCHEMA_VERSION


def test_schema_version_at_least_18():
    assert SCHEMA_VERSION >= 18


def test_migration_from_17_backfills_external(tmp_path: Path):
    """Simulate schema 17 DB with only platform_* filled → open with v18 → external_* set."""
    db_path = tmp_path / "legacy.sqlite"
    # minimal pre-v18-ish: create via Database then lower version + platform data
    db = Database(str(db_path))
    with db.conn() as c:
        c.execute(
            "INSERT INTO entity_platform_status "
            "(entity_type, entity_id, platform, status, legacy_post_id, legacy_scheduled_for) "
            "VALUES ('short', 1, 'youtube', 'scheduled', 'PID99', '2026-03-10T16:00:00+00:00')"
        )
        c.execute(
            "UPDATE system_state SET value='17' WHERE key='schema_version'"
        )
    # re-open triggers migration
    db2 = Database(str(db_path))
    row = db2.fetchone(
        "SELECT external_id, scheduled_for, source FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=1 AND platform='youtube'"
    )
    assert row["external_id"] == "PID99"
    assert row["scheduled_for"] and "2026-03-10" in row["scheduled_for"]
    ver = db2.fetchone("SELECT value FROM system_state WHERE key='schema_version'")
    assert int(ver["value"]) >= 18


def test_media_host_objects_table(tmp_path: Path):
    db = Database(str(tmp_path / "m.sqlite"))
    with db.conn() as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "media_host_objects" in tables
