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

CREATE TABLE IF NOT EXISTS platform_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engine TEXT NOT NULL,
    platform TEXT NOT NULL,
    platform_video_id TEXT NOT NULL,
    url TEXT,
    title TEXT,
    description TEXT,
    published_at TEXT,
    duration_sec REAL,
    width INTEGER,
    height INTEGER,
    thumbnail_url TEXT,
    origin TEXT NOT NULL DEFAULT 'manual',
    match_status TEXT NOT NULL DEFAULT 'unmatched',
    confidence REAL,
    matched_entity_type TEXT,
    matched_entity_id INTEGER,
    claim_status TEXT NOT NULL DEFAULT 'unknown',
    claim_info TEXT,
    edit_error TEXT,
    raw_json TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(engine, platform, platform_video_id)
);

CREATE INDEX IF NOT EXISTS idx_eps_platform_sched
    ON entity_platform_status(platform, postiz_scheduled_for);
CREATE INDEX IF NOT EXISTS idx_eps_status
    ON entity_platform_status(status);
CREATE INDEX IF NOT EXISTS idx_shorts_parent
    ON shorts(parent_video_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_upload_confirmed
    ON platform_uploads(engine, platform, matched_entity_type, matched_entity_id)
    WHERE match_status = 'confirmed';
"""

SCHEMA_VERSION = 9



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

    def upsert_upload(
        self,
        engine: str,
        platform: str,
        external_id: str,
        url: str | None = None,
        title: str | None = None,
        description: str | None = None,
        published_at: str | None = None,
        duration_sec: float | None = None,
        width: int | None = None,
        height: int | None = None,
        thumbnail_url: str | None = None,
        origin: str = "manual",
        raw_json: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        self.execute(
            """
            INSERT INTO platform_uploads
                (engine, platform, platform_video_id, url, title, description, published_at,
                 duration_sec, width, height, thumbnail_url, origin, raw_json,
                 first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(engine, platform, platform_video_id) DO UPDATE SET
                url=COALESCE(excluded.url, platform_uploads.url),
                title=COALESCE(excluded.title, platform_uploads.title),
                description=COALESCE(excluded.description, platform_uploads.description),
                published_at=COALESCE(excluded.published_at, platform_uploads.published_at),
                duration_sec=COALESCE(excluded.duration_sec, platform_uploads.duration_sec),
                width=COALESCE(excluded.width, platform_uploads.width),
                height=COALESCE(excluded.height, platform_uploads.height),
                thumbnail_url=COALESCE(excluded.thumbnail_url, platform_uploads.thumbnail_url),
                origin=excluded.origin,
                raw_json=COALESCE(excluded.raw_json, platform_uploads.raw_json),
                last_seen_at=excluded.last_seen_at
            """,
            (engine, platform, external_id, url, title, description, published_at,
             duration_sec, width, height, thumbnail_url, origin, raw_json, now, now),
        )
        return self.fetchone(
            "SELECT * FROM platform_uploads WHERE engine=? AND platform=? AND platform_video_id=?",
            (engine, platform, external_id),
        )

    def get_upload(self, upload_id: int) -> dict[str, Any] | None:
        return self.fetchone("SELECT * FROM platform_uploads WHERE id=?", (upload_id,))

    def list_uploads(
        self, status: str | None = None, platform: str | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM platform_uploads WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND match_status=?"
            params.append(status)
        if platform:
            sql += " AND platform=?"
            params.append(platform)
        sql += " ORDER BY COALESCE(published_at, first_seen_at) DESC"
        return self.fetchall(sql, tuple(params))

    def set_upload_match(
        self,
        upload_id: int,
        entity_type: str | None,
        entity_id: int | None,
        confidence: float | None = None,
        status: str = "confirmed",
    ) -> None:
        self.execute(
            "UPDATE platform_uploads SET match_status=?, matched_entity_type=?, "
            "matched_entity_id=?, confidence=?, last_seen_at=? WHERE id=?",
            (status, entity_type, entity_id, confidence, _utc_now(), upload_id),
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
