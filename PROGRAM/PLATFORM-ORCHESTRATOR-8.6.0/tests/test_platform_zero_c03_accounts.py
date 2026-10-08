"""platform-zero COMMIT 3: platform_accounts."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.accounts.store import PlatformAccountStore  # noqa: E402


class _MemDB:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE platform_accounts (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                external_account_id TEXT NOT NULL DEFAULT '',
                name TEXT DEFAULT '',
                username TEXT DEFAULT '',
                project_id TEXT DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                auth_provider TEXT DEFAULT '',
                token_ref TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
        """)

    def close(self):
        if getattr(self, "conn", None) is not None:
            self.conn.close()
            self.conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def execute(self, sql, params=()):
        self.conn.execute(sql, params)
        self.conn.commit()

    def fetchone(self, sql, params=()):
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def fetchall(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]


def test_upsert_and_get():
    store = PlatformAccountStore(_MemDB())
    a = store.upsert(
        platform="youtube", external_account_id="UC123",
        name="Main", username="@main", project_id="p1",
        token_ref="tokens/youtube.json",
    )
    assert a.id
    assert a.platform == "youtube"
    got = store.get(a.id)
    assert got and got.external_account_id == "UC123"


def test_upsert_updates_same_external():
    store = PlatformAccountStore(_MemDB())
    a1 = store.upsert(platform="youtube", external_account_id="UC1", name="A")
    a2 = store.upsert(platform="youtube", external_account_id="UC1", name="B")
    assert a1.id == a2.id
    assert a2.name == "B"


def test_list_filter_project_enabled():
    store = PlatformAccountStore(_MemDB())
    store.upsert(platform="youtube", external_account_id="1", project_id="p1")
    store.upsert(platform="telegram", external_account_id="2", project_id="p1")
    store.upsert(platform="youtube", external_account_id="3", project_id="p2", enabled=False)
    assert len(store.list(project_id="p1")) == 2
    assert len(store.list(platform="youtube", enabled_only=True)) == 1


def test_set_enabled():
    store = PlatformAccountStore(_MemDB())
    a = store.upsert(platform="tiktok", external_account_id="tt1")
    store.set_enabled(a.id, False)
    assert store.get(a.id).enabled is False
