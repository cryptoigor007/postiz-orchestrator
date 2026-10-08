from __future__ import annotations

import sqlite3
from pathlib import Path
from contextlib import closing

from orchestrator.db import Database, SCHEMA_VERSION


def test_fresh_eps_is_account_aware(tmp_path):
    db=Database(tmp_path / "fresh.sqlite")
    rows=db.fetchall("PRAGMA table_info(entity_platform_status)")
    account=[r for r in rows if r["name"]=="account_id"]
    assert account
    assert int(account[0]["pk"])==4
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES(?,?,?,?,?)",("short",1,"instagram","a","ready"))
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES(?,?,?,?,?)",("short",1,"instagram","b","ready"))
    assert len(db.fetchall("SELECT * FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND platform=?",("short",1,"instagram")))==2


def test_old_schema_migrates_to_account_aware(tmp_path):
    path=Path(tmp_path)/"old.sqlite"
    with closing(sqlite3.connect(path)) as con:
        con.execute("CREATE TABLE system_state(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)")
        con.execute("CREATE TABLE entity_platform_status(entity_type TEXT NOT NULL,entity_id INTEGER NOT NULL,platform TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ready',legacy_post_id TEXT,legacy_scheduled_for TEXT,published_at TEXT,release_url TEXT,last_error TEXT,PRIMARY KEY(entity_type,entity_id,platform))")
        con.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,status,legacy_post_id) VALUES('short',1,'youtube','published','old-1')")
        con.execute("INSERT INTO system_state(key,value,updated_at) VALUES('schema_version','21','now')")
        con.commit()
    db=Database(path)
    row=db.fetchone("SELECT account_id, external_id FROM entity_platform_status WHERE entity_type='short' AND entity_id=1 AND platform='youtube'")
    assert row["account_id"]==""
    assert row["external_id"]=="old-1"
    assert int(db.get_setting("schema_version"))==SCHEMA_VERSION
