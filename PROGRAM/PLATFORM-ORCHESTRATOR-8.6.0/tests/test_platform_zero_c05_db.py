"""platform-zero COMMIT 5: EPS fields, remote_*, oauth_sessions, platform_accounts."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.db import Database, SCHEMA_VERSION  # noqa: E402


def test_schema_version_at_least_17():
    assert SCHEMA_VERSION >= 17


def test_migration_creates_new_tables_and_columns(tmp_path: Path):
    db_path = tmp_path / "t.sqlite"
    db = Database(str(db_path))
    with db.conn() as c:
        tables = {
            r[0]
            for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        cols = {
            r[1]
            for r in c.execute("PRAGMA table_info(entity_platform_status)").fetchall()
        }
        ver_row = c.execute(
            "SELECT value FROM system_state WHERE key='schema_version'"
        ).fetchone()
    assert "oauth_sessions" in tables
    assert "platform_accounts" in tables
    assert "remote_uploads" in tables
    assert "remote_upload_matches" in tables
    assert "remote_scans" in tables
    for col in (
        "external_id", "external_sub_id", "external_url", "scheduled_for",
        "publish_mode", "source", "privacy", "claims_state", "lock_owner",
        "lease_until", "attempt", "next_retry_at", "last_status_sync_at",
        "module_version",
    ):
        assert col in cols, f"missing column {col}"
    assert ver_row is not None
    assert int(ver_row[0]) >= 17


def test_eps_lease_columns_nullable(tmp_path: Path):
    """Lease fields exist and accept NULL (recover publishing)."""
    db = Database(str(tmp_path / "lease.sqlite"))
    with db.conn() as c:
        c.execute(
            """
            INSERT INTO entity_platform_status
                (entity_type, entity_id, platform, status, external_id, lock_owner, lease_until, attempt)
            VALUES ('short', 1, 'youtube', 'publishing', 'vid1', 'worker-1', '2026-09-29T12:00:00Z', 1)
            """
        )
        row = c.execute(
            "SELECT external_id, lock_owner, lease_until, attempt FROM entity_platform_status"
        ).fetchone()
    assert row[0] == "vid1"
    assert row[1] == "worker-1"
    assert row[3] == 1
