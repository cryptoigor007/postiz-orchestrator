from __future__ import annotations

import sqlite3
from pathlib import Path
import re


def test_db_sets_explicit_busy_timeout(tmp_path: Path):
    from orchestrator.db import Database
    db = Database(tmp_path / "busy.sqlite")
    with db._connect() as conn:
        assert int(conn.execute("PRAGMA busy_timeout").fetchone()[0]) == 30000


def test_publisher_outbox_aggregate_key_is_account_scoped():
    src = Path("src/orchestrator/publisher.py").read_text()
    assert 'aggregate_key = f"{entity_type}:{entity_id}:{platform}:{account_id}"' in src
    assert '"publish.completed", aggregate_key, aggregate_key' in src


def test_no_embedded_ssh_host_ip_literals_in_scripts():
    bad = []
    pat = re.compile(r"root@(?:\d{1,3}\.){3}\d{1,3}")
    for f in Path("scripts").rglob("*.sh"):
        text = f.read_text()
        if pat.search(text):
            bad.append(str(f))
    assert not bad, bad


def test_db_connect_context_closes_handle(tmp_path):
    from orchestrator.db import Database
    db = Database(tmp_path / "close.sqlite")
    conn = db._connect()
    with conn:
        conn.execute("SELECT 1")
    try:
        conn.execute("SELECT 1")
    except Exception as exc:
        assert isinstance(exc, (sqlite3.ProgrammingError,))
    else:
        raise AssertionError("managed Database connection was not closed")
