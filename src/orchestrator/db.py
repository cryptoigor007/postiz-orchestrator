from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Iterable


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS long_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    folder_path TEXT NOT NULL UNIQUE,
    title TEXT,
    wide_path TEXT,
    vertical_path TEXT,
    title_text TEXT,
    description_text TEXT,
    hashtags_text TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shorts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    parent_video_id INTEGER REFERENCES long_videos(id),
    folder_path TEXT NOT NULL UNIQUE,
    order_index INTEGER DEFAULT 0,
    video_path TEXT,
    cover_path TEXT,
    title_text TEXT,
    description_text TEXT,
    hashtags_text TEXT,
    hook_text TEXT,
    upload_text TEXT,
    meta_text TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_platform_status (
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready',
    postiz_post_id TEXT,
    postiz_scheduled_for TEXT,
    published_at TEXT,
    release_url TEXT,
    link_updated_at TEXT,
    last_error TEXT,
    PRIMARY KEY (entity_type, entity_id, platform)
);

CREATE TABLE IF NOT EXISTS platform_queue_state (
    platform TEXT PRIMARY KEY,
    active_long_video_id INTEGER,
    series_tail_mode INTEGER DEFAULT 0,
    last_long_video_at TEXT,
    pending_series_end_question INTEGER DEFAULT 0,
    pending_series_end_at TEXT,
    last_series_end_question_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS platform_safety_state (
    platform TEXT PRIMARY KEY,
    is_paused INTEGER DEFAULT 0,
    paused_at TEXT,
    pause_reason TEXT,
    last_post_at TEXT,
    posts_today INTEGER DEFAULT 0,
    posts_today_date TEXT,
    warmup_until TEXT,
    last_error TEXT,
    last_error_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS publish_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT,
    entity_id INTEGER,
    platform TEXT,
    action TEXT,
    details TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_eps_platform_sched
    ON entity_platform_status(platform, postiz_scheduled_for);
CREATE INDEX IF NOT EXISTS idx_eps_status
    ON entity_platform_status(status);
CREATE INDEX IF NOT EXISTS idx_shorts_parent
    ON shorts(parent_video_id);
"""

SCHEMA_VERSION = 8



def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn) -> None:
        row = conn.execute(
            "SELECT value FROM system_state WHERE key='schema_version'"
        ).fetchone()
        current = int(row[0]) if row else 0
        if current < 8:
            conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_eps_platform_sched
                    ON entity_platform_status(platform, postiz_scheduled_for);
                CREATE INDEX IF NOT EXISTS idx_eps_status
                    ON entity_platform_status(status);
                CREATE INDEX IF NOT EXISTS idx_shorts_parent
                    ON shorts(parent_video_id);
            """)
        if current < SCHEMA_VERSION or current == 0:
            conn.execute(
                "INSERT INTO system_state (key, value, updated_at) VALUES ('schema_version', ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (str(SCHEMA_VERSION), _utc_now()),
            )


    @contextmanager
    def conn(self) -> Generator[sqlite3.Connection, None, None]:
        c = self._connect()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def execute(self, sql: str, params: tuple | dict = ()) -> None:
        with self.conn() as c:
            c.execute(sql, params)

    def executemany(self, sql: str, seq: Iterable) -> None:
        with self.conn() as c:
            c.executemany(sql, seq)

    def fetchone(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        with self.conn() as c:
            row = c.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    def log(self, entity_type: str, entity_id: int | None, platform: str | None,
            action: str, details: str = "") -> None:
        self.execute(
            "INSERT INTO publish_log (entity_type, entity_id, platform, action, details, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entity_type, entity_id, platform, action, details, _utc_now()),
        )

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.fetchone("SELECT value FROM system_state WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO system_state (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, _utc_now()),
        )

    def ensure_platform_states(self, platforms: list[str]) -> None:
        now = _utc_now()
        with self.conn() as c:
            for p in platforms:
                c.execute(
                    "INSERT OR IGNORE INTO platform_queue_state (platform, updated_at) VALUES (?, ?)",
                    (p, now),
                )
                c.execute(
                    "INSERT OR IGNORE INTO platform_safety_state (platform, updated_at) VALUES (?, ?)",
                    (p, now),
                )
