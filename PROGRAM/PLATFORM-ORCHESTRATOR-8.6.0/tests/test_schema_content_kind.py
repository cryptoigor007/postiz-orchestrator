"""SCHEMA 20: content_kind column + version control (§2.1)."""
from __future__ import annotations

from pathlib import Path

from orchestrator.db import SCHEMA_VERSION, Database


def test_schema_version_is_at_least_20():
    assert SCHEMA_VERSION >= 20


def test_content_kind_column_on_fresh_db(tmp_path: Path):
    db_path = tmp_path / "t.sqlite"
    db = Database(str(db_path))
    with db.conn() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(entity_platform_status)").fetchall()}
        ver = c.execute(
            "SELECT value FROM system_state WHERE key='schema_version'"
        ).fetchone()
    assert "content_kind" in cols
    assert ver is not None
    assert int(ver[0]) == SCHEMA_VERSION


def test_schema_not_downgraded(tmp_path: Path):
    """Opening current DB keeps SCHEMA_VERSION (no silent downgrade)."""
    db_path = tmp_path / "cur.sqlite"
    db = Database(str(db_path))
    with db.conn() as c:
        ver1 = c.execute(
            "SELECT value FROM system_state WHERE key='schema_version'"
        ).fetchone()[0]
    db2 = Database(str(db_path))
    with db2.conn() as c:
        ver2 = c.execute(
            "SELECT value FROM system_state WHERE key='schema_version'"
        ).fetchone()[0]
    assert ver1 == ver2 == str(SCHEMA_VERSION)
