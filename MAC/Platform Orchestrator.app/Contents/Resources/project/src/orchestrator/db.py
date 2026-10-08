from __future__ import annotations

import logging
import sqlite3
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class _ManagedConnection(sqlite3.Connection):
    """Connection whose context-manager exit also closes the handle."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


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
    platform_paths TEXT,
    cover_path TEXT,
    scan_ignored INTEGER DEFAULT 0,
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
    platform_paths TEXT,
    scan_ignored INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_platform_status (
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL DEFAULT '', 
    status TEXT NOT NULL DEFAULT 'ready',
    legacy_post_id TEXT,
    legacy_scheduled_for TEXT,
    published_at TEXT,
    release_url TEXT,
    link_updated_at TEXT,
    last_error TEXT,
    deleted_at TEXT,
    deleted_reason TEXT,
    cascade_from TEXT,
    PRIMARY KEY (entity_type, entity_id, platform, account_id)
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


CREATE TABLE IF NOT EXISTS platform_safety_account_state (
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL,
    is_paused INTEGER DEFAULT 0,
    paused_at TEXT,
    pause_reason TEXT,
    last_post_at TEXT,
    posts_today INTEGER DEFAULT 0,
    posts_today_date TEXT,
    warmup_until TEXT,
    last_error TEXT,
    last_error_at TEXT,
    updated_at TEXT,
    PRIMARY KEY (platform, account_id)
);

CREATE TABLE IF NOT EXISTS platform_queue_account_state (
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL,
    active_long_video_id INTEGER,
    series_tail_mode INTEGER DEFAULT 0,
    last_long_video_at TEXT,
    pending_series_end_question INTEGER DEFAULT 0,
    pending_series_end_at TEXT,
    last_series_end_question_at TEXT,
    pending_backlog_question INTEGER DEFAULT 0,
    pending_backlog_at TEXT,
    updated_at TEXT,
    PRIMARY KEY(platform, account_id)
);

CREATE TABLE IF NOT EXISTS webapp_rate_limits (
    identity TEXT NOT NULL,
    window_started_at REAL NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(identity)
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
    ON entity_platform_status(platform, legacy_scheduled_for);
CREATE INDEX IF NOT EXISTS idx_eps_status
    ON entity_platform_status(status);
CREATE INDEX IF NOT EXISTS idx_shorts_parent
    ON shorts(parent_video_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_upload_confirmed
    ON platform_uploads(engine, platform, matched_entity_type, matched_entity_id)
    WHERE match_status = 'confirmed';

CREATE TABLE IF NOT EXISTS provider_health (
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'unknown',
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_success_at REAL,
    last_failure_at REAL,
    last_error TEXT,
    updated_at REAL NOT NULL,
    PRIMARY KEY (platform, account_id)
);

CREATE TABLE IF NOT EXISTS provider_access (
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'NOT_CONFIGURED',
    credentials_ok INTEGER NOT NULL DEFAULT 0,
    redirect_ok INTEGER NOT NULL DEFAULT 0,
    account_ok INTEGER NOT NULL DEFAULT 0,
    token_ok INTEGER NOT NULL DEFAULT 0,
    scopes_ok INTEGER NOT NULL DEFAULT 0,
    business_verification_ok INTEGER NOT NULL DEFAULT 0,
    app_review_ok INTEGER NOT NULL DEFAULT 0,
    audit_ok INTEGER NOT NULL DEFAULT 0,
    webhook_ok INTEGER NOT NULL DEFAULT 0,
    media_host_ok INTEGER NOT NULL DEFAULT 1,
    smoke_test_ok INTEGER NOT NULL DEFAULT 0,
    live_ok INTEGER NOT NULL DEFAULT 0,
    details TEXT,
    updated_at REAL NOT NULL,
    PRIMARY KEY (platform, account_id)
);

CREATE TABLE IF NOT EXISTS publish_attempts (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL DEFAULT '',
    revision_hash TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL,
    provider_request_id TEXT,
    upload_session_id TEXT,
    remote_object_id TEXT,
    status TEXT NOT NULL DEFAULT 'started',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error_code TEXT,
    error_message TEXT,
    UNIQUE(platform, account_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS outbox_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    published_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    last_error TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending
    ON outbox_events(status, locked_until, attempts, id);

CREATE TABLE IF NOT EXISTS webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    account_id TEXT NOT NULL DEFAULT '',
    event_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    signature_valid INTEGER NOT NULL DEFAULT 0,
    received_at TEXT NOT NULL,
    processed_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    payload_json TEXT NOT NULL,
    UNIQUE(provider, account_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_webhook_pending
    ON webhook_events(processed_at, attempts, received_at);

CREATE TABLE IF NOT EXISTS durable_jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT '',
    account_id TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TEXT NOT NULL,
    locked_until TEXT,
    worker_id TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_durable_jobs_ready
    ON durable_jobs(status, available_at, locked_until);

CREATE TABLE IF NOT EXISTS distribution_targets (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL,
    revision_hash TEXT NOT NULL,
    scheduled_for TEXT,
    publish_mode TEXT NOT NULL DEFAULT 'immediate',
    status TEXT NOT NULL DEFAULT 'queued',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(entity_type, entity_id, platform, account_id, revision_hash)
);

CREATE TABLE IF NOT EXISTS media_artifacts (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    path TEXT,
    kind TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    storage_provider TEXT,
    remote_url TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    deleted_at TEXT,
    UNIQUE(sha256, kind, size_bytes)
);

CREATE TABLE IF NOT EXISTS consistency_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    account_id TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    scanned INTEGER NOT NULL DEFAULT 0,
    repaired INTEGER NOT NULL DEFAULT 0,
    conflicts INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running',
    error TEXT
);
"""

SCHEMA_VERSION = 28



def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, factory=_ManagedConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    @staticmethod
    def _add_column_strict(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column in cols:
            return
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        except Exception as exc:
            raise RuntimeError(f"critical migration failed: {table}.{column}: {exc}") from exc

    def _migrate(self, conn) -> None:
        row = conn.execute(
            "SELECT value FROM system_state WHERE key='schema_version'"
        ).fetchone()
        current = int(row[0]) if row else 0
        # D11: перед изменением схемы делаем файловый бэкап (миграции только вперёд)
        if current and current < SCHEMA_VERSION:
            try:
                import shutil as _shutil
                from pathlib import Path as _P

                src = _P(self.path)
                if src.is_file() and src.stat().st_size > 0:
                    bdir = src.parent.parent / "backups"
                    bdir.mkdir(parents=True, exist_ok=True)
                    dst = bdir / f"pre_migration_v{current}_to_v{SCHEMA_VERSION}_{_utc_now().replace(':', '').replace('-', '')}.sqlite"
                    _shutil.copy2(src, dst)
            except Exception as exc:
                logger.debug("pre-migration backup failed: %s", type(exc).__name__)
        if current < 8:
            conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_eps_platform_sched
                    ON entity_platform_status(platform, legacy_scheduled_for);
                CREATE INDEX IF NOT EXISTS idx_eps_status
                    ON entity_platform_status(status);
                CREATE INDEX IF NOT EXISTS idx_shorts_parent
                    ON shorts(parent_video_id);
            """)
        if current < 10:
            for stmt in (
                "ALTER TABLE long_videos ADD COLUMN platform_paths TEXT",
                "ALTER TABLE shorts ADD COLUMN platform_paths TEXT",
            ):
                try:
                    conn.execute(stmt)
                except Exception as exc:
                    logger.debug("legacy migration statement skipped: %s", type(exc).__name__)
        if current < 11:
            try:
                conn.execute("ALTER TABLE long_videos ADD COLUMN cover_path TEXT")
            except Exception as exc:
                logger.debug("legacy migration compatibility path skipped: %s", type(exc).__name__)
            try:
                conn.execute("ALTER TABLE long_videos ADD COLUMN placement TEXT")
            except Exception as exc:
                logger.debug("legacy migration compatibility path skipped: %s", type(exc).__name__)
            try:
                conn.execute("ALTER TABLE shorts ADD COLUMN placement TEXT")
            except Exception as exc:
                logger.debug("legacy migration compatibility path skipped: %s", type(exc).__name__)
        if current < 12:
            # R3: unique legacy_post_id where set (prevents silent double-bind)
            try:
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_eps_platform_id_unique "
                    "ON entity_platform_status(legacy_post_id) "
                    "WHERE legacy_post_id IS NOT NULL AND legacy_post_id != ''"
                )
            except Exception as exc:
                logger.debug("legacy migration compatibility path skipped: %s", type(exc).__name__)
        if current < 13:
            # P0.9: отдельные поля для backlog-вопроса (раньше делились с soft-end)
            for stmt in (
                "ALTER TABLE platform_queue_state ADD COLUMN pending_backlog_question INTEGER DEFAULT 0",
                "ALTER TABLE platform_queue_state ADD COLUMN pending_backlog_at TEXT",
            ):
                try:
                    conn.execute(stmt)
                except Exception as exc:
                    logger.debug("legacy migration statement skipped: %s", type(exc).__name__)
            # эвристика миграции: до v13 pending ставил только backlog → переносим, series_end чистим
            try:
                conn.execute(
                    "UPDATE platform_queue_state SET "
                    "pending_backlog_question=COALESCE(pending_series_end_question,0), "
                    "pending_backlog_at=pending_series_end_at, "
                    "pending_series_end_question=0, pending_series_end_at=NULL "
                    "WHERE COALESCE(pending_series_end_question,0)=1"
                )
            except Exception as exc:
                logger.debug("legacy migration compatibility path skipped: %s", type(exc).__name__)
        if current < 14:
            # Корзина: мягкое удаление (tombstone) вместо безвозвратного DELETE.
            # Файлы на диске не трогаем; scan_ignored защищает от повторной регистрации
            # после «очистить корзину».
            for stmt in (
                "ALTER TABLE entity_platform_status ADD COLUMN deleted_at TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN deleted_reason TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN cascade_from TEXT",
                "ALTER TABLE long_videos ADD COLUMN scan_ignored INTEGER DEFAULT 0",
                "ALTER TABLE shorts ADD COLUMN scan_ignored INTEGER DEFAULT 0",
            ):
                try:
                    conn.execute(stmt)
                except Exception:
                    logger.debug("migration v14: %s уже применено", stmt, exc_info=True)
        if current < 15:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS oauth_sessions (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    state_hash TEXT NOT NULL,
                    code_verifier TEXT NOT NULL,
                    account_hint TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    consumed_at REAL,
                    redirect_uri TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_oauth_sessions_state
                    ON oauth_sessions(state_hash);
                CREATE INDEX IF NOT EXISTS idx_oauth_sessions_provider
                    ON oauth_sessions(provider, expires_at);
            """)

        if current < 16:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS platform_accounts (
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
                CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_accounts_ext
                    ON platform_accounts(platform, external_account_id)
                    WHERE external_account_id != '';
                CREATE INDEX IF NOT EXISTS idx_platform_accounts_project
                    ON platform_accounts(project_id, platform);
            """)

        if current < 17:
            # platform-zero C5: EPS extensions, remote inventory, leases
            for stmt in (
                "ALTER TABLE entity_platform_status ADD COLUMN external_id TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN external_sub_id TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN external_url TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN scheduled_for TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN publish_mode TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN source TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN privacy TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN claims_state TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN claims_checked_at TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN lock_owner TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN lease_until TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN attempt INTEGER DEFAULT 0",
                "ALTER TABLE entity_platform_status ADD COLUMN next_retry_at TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN last_status_sync_at TEXT",
                "ALTER TABLE entity_platform_status ADD COLUMN module_version TEXT",
            ):
                try:
                    conn.execute(stmt)
                except Exception as exc:
                    logger.debug("legacy migration statement skipped: %s", type(exc).__name__)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS remote_uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    url TEXT,
                    title TEXT,
                    description TEXT,
                    published_at TEXT,
                    scheduled_for TEXT,
                    privacy TEXT,
                    status TEXT,
                    duration_sec REAL,
                    thumb_url TEXT,
                    media_type TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    raw_json TEXT,
                    UNIQUE(platform, external_id)
                );
                CREATE TABLE IF NOT EXISTS remote_upload_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    remote_upload_id INTEGER NOT NULL REFERENCES remote_uploads(id),
                    entity_type TEXT,
                    entity_id INTEGER,
                    score REAL,
                    score_parts_json TEXT,
                    decision TEXT,
                    decided_at TEXT,
                    decided_by TEXT,
                    UNIQUE(remote_upload_id, entity_type, entity_id)
                );
                CREATE TABLE IF NOT EXISTS remote_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    account_id TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    lookback_days INTEGER,
                    pages INTEGER DEFAULT 0,
                    items_seen INTEGER DEFAULT 0,
                    cursor TEXT,
                    partial INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    error TEXT,
                    scan_reason TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_eps_external_id
                    ON entity_platform_status(platform, external_id);
                CREATE INDEX IF NOT EXISTS idx_eps_lease
                    ON entity_platform_status(lease_until);
                CREATE INDEX IF NOT EXISTS idx_eps_scheduled_for
                    ON entity_platform_status(scheduled_for);
            """)


        if current < 18:
            # F4: platform_* retirement — backfill external_* from platform_*, stop requiring platform cols
            # Columns legacy_post_id / legacy_scheduled_for remain nullable (no DROP for SQLite
            # compatibility); new writes must use external_* only (see publisher F3).
            try:
                conn.execute(
                    """
                    UPDATE entity_platform_status
                    SET external_id = legacy_post_id
                    WHERE (external_id IS NULL OR external_id = '')
                      AND legacy_post_id IS NOT NULL AND legacy_post_id != ''
                      AND legacy_post_id NOT LIKE 'tg:%'
                    """
                )
                conn.execute(
                    """
                    UPDATE entity_platform_status
                    SET scheduled_for = legacy_scheduled_for
                    WHERE (scheduled_for IS NULL OR scheduled_for = '')
                      AND legacy_scheduled_for IS NOT NULL AND legacy_scheduled_for != ''
                    """
                )
                conn.execute(
                    """
                    UPDATE entity_platform_status
                    SET source = COALESCE(NULLIF(source, ''), 'legacy_platform')
                    WHERE legacy_post_id IS NOT NULL AND legacy_post_id != ''
                      AND (source IS NULL OR source = '')
                    """
                )
            except Exception as exc:
                logger.debug("legacy migration compatibility path skipped: %s", type(exc).__name__)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS media_host_objects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL DEFAULT 'b2',
                    file_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    url TEXT,
                    entity_type TEXT,
                    entity_id INTEGER,
                    platform TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    deleted_at TEXT,
                    status TEXT NOT NULL DEFAULT 'active'
                );
                CREATE INDEX IF NOT EXISTS idx_media_host_expires
                    ON media_host_objects(expires_at) WHERE deleted_at IS NULL;
                CREATE INDEX IF NOT EXISTS idx_media_host_file
                    ON media_host_objects(file_id);
            """)


        if current < 19:
            # Rename historical transport columns (if present) to legacy_*
            for old, new in (
                ("postiz_post_id", "legacy_post_id"),
                ("postiz_scheduled_for", "legacy_scheduled_for"),
            ):
                try:
                    cols = {r[1] for r in conn.execute(
                        "PRAGMA table_info(entity_platform_status)").fetchall()}
                    if old in cols and new not in cols:
                        conn.execute(
                            f"ALTER TABLE entity_platform_status RENAME COLUMN {old} TO {new}"
                        )
                    elif old in cols and new in cols:
                        # both exist: copy then we leave old (SQLite can't DROP easily)
                        conn.execute(
                            f"UPDATE entity_platform_status SET {new} = COALESCE({new}, {old}) "
                            f"WHERE ({new} IS NULL OR {new} = '') AND {old} IS NOT NULL"
                        )
                except Exception as exc:
                    logger.debug("legacy migration statement skipped: %s", type(exc).__name__)


        if current < 20:
            # KIND-01: first-class content_kind on EPS
            for stmt in (
                "ALTER TABLE entity_platform_status ADD COLUMN content_kind TEXT",
            ):
                try:
                    conn.execute(stmt)
                except Exception as exc:
                    logger.debug("legacy migration statement skipped: %s", type(exc).__name__)
            try:
                conn.execute(
                    """
                    UPDATE entity_platform_status
                    SET content_kind = COALESCE(NULLIF(content_kind, ''), 'video_native')
                    WHERE content_kind IS NULL OR content_kind = ''
                    """
                )
            except Exception as exc:
                logger.debug("legacy migration compatibility path skipped: %s", type(exc).__name__)

        if current < 21:
            # Foundation for the independent social stack.  These fields/tables are
            # additive and do not change the current EPS primary key yet; the full
            # account-aware EPS rebuild is a separate cutover because SQLite requires
            # a table rebuild and the legacy 3-column conflict queries must be migrated
            # atomically with it.
            self._add_column_strict(conn, "oauth_sessions", "claimed_at", "REAL")
            self._add_column_strict(conn, "oauth_sessions", "claim_token", "TEXT")
            for column, definition in (
                ("connection_state", "TEXT NOT NULL DEFAULT 'NOT_CONFIGURED'"),
                ("granted_scopes", "TEXT NOT NULL DEFAULT ''"),
                ("expires_at", "REAL"),
                ("refresh_status", "TEXT NOT NULL DEFAULT 'unknown'"),
                ("webhook_status", "TEXT NOT NULL DEFAULT 'unknown'"),
                ("review_state", "TEXT NOT NULL DEFAULT 'unknown'"),
                ("app_id", "TEXT NOT NULL DEFAULT ''"),
            ):
                self._add_column_strict(conn, "platform_accounts", column, definition)
            # Verify all foundation tables exist rather than silently proceeding.
            required_tables = {
                "provider_health", "provider_access", "publish_attempts",
                "outbox_events", "webhook_events", "durable_jobs",
                "distribution_targets", "media_artifacts", "consistency_runs",
            }
            existing_tables = {
                str(r[0]) for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            missing_tables = sorted(required_tables - existing_tables)
            if missing_tables:
                raise RuntimeError(f"foundation schema incomplete: {missing_tables}")

        if current < 22:
            # Account-aware EPS cutover. SQLite requires a table rebuild to change the
            # primary key from (entity_type, entity_id, platform) to include account_id.
            cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(entity_platform_status)").fetchall()}
            pk_cols = [str(r[1]) for r in sorted(
                conn.execute("PRAGMA table_info(entity_platform_status)").fetchall(),
                key=lambda r: int(r[5] or 0),
            ) if int(r[5] or 0) > 0]
            if "account_id" not in cols or pk_cols != ["entity_type", "entity_id", "platform", "account_id"]:
                old_cols = [str(r[1]) for r in conn.execute("PRAGMA table_info(entity_platform_status)").fetchall()]
                required = {"entity_type", "entity_id", "platform", "status"}
                missing_old = sorted(required - set(old_cols))
                if missing_old:
                    raise RuntimeError(f"EPS rebuild missing columns: {missing_old}")
                conn.execute("DROP TABLE IF EXISTS entity_platform_status_v22_new")
                conn.execute("""
                    CREATE TABLE entity_platform_status_v22_new (
                        entity_type TEXT NOT NULL,
                        entity_id INTEGER NOT NULL,
                        platform TEXT NOT NULL,
                        account_id TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'ready',
                        legacy_post_id TEXT,
                        legacy_scheduled_for TEXT,
                        published_at TEXT,
                        release_url TEXT,
                        link_updated_at TEXT,
                        last_error TEXT,
                        deleted_at TEXT,
                        deleted_reason TEXT,
                        cascade_from TEXT,
                        external_id TEXT,
                        external_sub_id TEXT,
                        external_url TEXT,
                        scheduled_for TEXT,
                        publish_mode TEXT,
                        source TEXT,
                        privacy TEXT,
                        claims_state TEXT,
                        claims_checked_at TEXT,
                        lock_owner TEXT,
                        lease_until TEXT,
                        attempt INTEGER DEFAULT 0,
                        next_retry_at TEXT,
                        last_status_sync_at TEXT,
                        module_version TEXT,
                        content_kind TEXT,
                        PRIMARY KEY (entity_type, entity_id, platform, account_id)
                    )
                """)
                # Copy every known column; absent historical columns become NULL/default.
                new_cols = [str(r[1]) for r in conn.execute("PRAGMA table_info(entity_platform_status_v22_new)").fetchall()]
                select_parts = []
                for c in new_cols:
                    if c == "external_id" and "legacy_post_id" in old_cols:
                        select_parts.append("legacy_post_id AS external_id")
                    elif c == "scheduled_for" and "legacy_scheduled_for" in old_cols:
                        select_parts.append("legacy_scheduled_for AS scheduled_for")
                    elif c in old_cols:
                        select_parts.append(c)
                    elif c == "account_id":
                        select_parts.append("'' AS account_id")
                    else:
                        select_parts.append("NULL AS " + c)
                conn.execute(
                    f"INSERT INTO entity_platform_status_v22_new ({', '.join(new_cols)}) "
                    f"SELECT {', '.join(select_parts)} FROM entity_platform_status"
                )
                # Preserve important indexes under fresh names after the swap.
                conn.execute("DROP TABLE entity_platform_status")
                conn.execute("ALTER TABLE entity_platform_status_v22_new RENAME TO entity_platform_status")
                conn.executescript("""
                    DROP INDEX IF EXISTS idx_eps_platform_sched;
                    CREATE INDEX IF NOT EXISTS idx_eps_platform_sched
                        ON entity_platform_status(platform, scheduled_for);
                    CREATE INDEX IF NOT EXISTS idx_eps_status
                        ON entity_platform_status(status);
                    CREATE INDEX IF NOT EXISTS idx_eps_external_id
                        ON entity_platform_status(platform, external_id);
                    CREATE INDEX IF NOT EXISTS idx_eps_lease
                        ON entity_platform_status(lease_until);
                    CREATE INDEX IF NOT EXISTS idx_eps_scheduled_for
                        ON entity_platform_status(scheduled_for);
                    CREATE INDEX IF NOT EXISTS idx_eps_account
                        ON entity_platform_status(platform, account_id, status);
                """)

        if current < 23:
            # C2: durable worker controls — max attempts, retry scheduling and completion timestamp.
            for column, definition in (
                ("max_attempts", "INTEGER NOT NULL DEFAULT 8"),
                ("next_retry_at", "TEXT"),
                ("finished_at", "TEXT"),
            ):
                self._add_column_strict(conn, "durable_jobs", column, definition)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_durable_jobs_retry ON durable_jobs(status, next_retry_at, available_at)")

        if current < 24:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS content_revisions (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER NOT NULL,
                    revision_hash TEXT NOT NULL UNIQUE,
                    content_json TEXT NOT NULL,
                    media_path TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_content_revisions_entity
                    ON content_revisions(entity_type, entity_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_distribution_target_status
                    ON distribution_targets(platform, account_id, status, scheduled_for);
            """)

        if current < 25:
            for column, definition in (
                ("processing_state", "TEXT NOT NULL DEFAULT 'queued'"),
                ("normalized_type", "TEXT"),
                ("external_id", "TEXT"),
                ("processed_result", "TEXT"),
            ):
                self._add_column_strict(conn, "webhook_events", column, definition)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_webhook_processing ON webhook_events(processing_state, received_at)")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS webhook_subscriptions (
                    provider TEXT NOT NULL,
                    account_id TEXT NOT NULL DEFAULT '',
                    endpoint TEXT NOT NULL,
                    desired INTEGER NOT NULL DEFAULT 1,
                    verified INTEGER NOT NULL DEFAULT 0,
                    last_checked_at TEXT,
                    last_error TEXT,
                    PRIMARY KEY(provider, account_id)
                );
            """)

        # N15: validate the current EPS contract before advertising the new schema version.
        # If this raises, the surrounding SQLite transaction rolls back the migration/version bump.
        _verify_eps_columns_conn(conn)
        if current < 26:
            # C1/C2: explicit outbox lifecycle state. Existing rows are backfilled from
            # the legacy published_at / DEAD_LETTER markers so dead events can never be
            # claimed again accidentally.
            self._add_column_strict(conn, "outbox_events", "status", "TEXT NOT NULL DEFAULT 'pending'")
            conn.execute("UPDATE outbox_events SET status='published' WHERE published_at IS NOT NULL")
            conn.execute("UPDATE outbox_events SET status='dead' WHERE last_error LIKE 'DEAD_LETTER:%'")
            conn.execute("DROP INDEX IF EXISTS idx_outbox_pending")
            conn.execute("CREATE INDEX idx_outbox_pending ON outbox_events(status, locked_until, attempts, id)")

        if current < 27:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS platform_safety_account_state (
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    is_paused INTEGER DEFAULT 0,
                    paused_at TEXT,
                    pause_reason TEXT,
                    last_post_at TEXT,
                    posts_today INTEGER DEFAULT 0,
                    posts_today_date TEXT,
                    warmup_until TEXT,
                    last_error TEXT,
                    last_error_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY(platform, account_id)
                );
                CREATE INDEX IF NOT EXISTS idx_safety_account_updated
                    ON platform_safety_account_state(platform, account_id, updated_at);
            """)

        if current < 28:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS platform_queue_account_state (
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    active_long_video_id INTEGER,
                    series_tail_mode INTEGER DEFAULT 0,
                    last_long_video_at TEXT,
                    pending_series_end_question INTEGER DEFAULT 0,
                    pending_series_end_at TEXT,
                    last_series_end_question_at TEXT,
                    pending_backlog_question INTEGER DEFAULT 0,
                    pending_backlog_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY(platform, account_id)
                );
                CREATE TABLE IF NOT EXISTS webapp_rate_limits (
                    identity TEXT NOT NULL,
                    window_started_at REAL NOT NULL,
                    request_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(identity)
                );
                CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON webapp_rate_limits(window_started_at);
            """)

        if current < SCHEMA_VERSION or current == 0:
            conn.execute(
                "INSERT INTO system_state (key, value, updated_at) VALUES ('schema_version', ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (str(SCHEMA_VERSION), _utc_now()),
            )


    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Run multiple related mutations in one SQLite transaction.

        Domain state and its outbox event can therefore commit or roll back
        together.  Callers must use the yielded connection for every statement
        that belongs to the transaction.
        """
        c = self._connect()
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    @contextmanager
    def conn(self) -> Generator[sqlite3.Connection, None, None]:
        with self.transaction() as c:
            yield c

    def execute(self, sql: str, params: tuple | dict = ()) -> int:
        with self.conn() as c:
            return int(c.execute(sql, params).rowcount)

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


    def set_content_kind(
        self,
        entity_type: str,
        entity_id: int,
        platform: str,
        content_kind: str,
        account_id: str = "",
    ) -> None:
        """KIND-01: persist content_kind on EPS row."""
        kind = (content_kind or "video_native").strip() or "video_native"
        self.execute(
            "UPDATE entity_platform_status SET content_kind=? "
            "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
            (kind, entity_type, entity_id, platform, account_id),
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


# N15: critical column presence check
_CRITICAL_EPS_COLS = (
    "external_id", "external_url", "publish_mode", "content_kind",
    "scheduled_for", "status", "lease_until", "last_error", "account_id",
)

def _verify_eps_columns_conn(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(entity_platform_status)").fetchall()
    names = {str(r[1]) for r in rows}
    missing = [c for c in _CRITICAL_EPS_COLS if c not in names]
    if missing:
        raise RuntimeError(f"schema incomplete, missing EPS columns: {missing}")

def verify_eps_schema(db: "Database") -> None:
    """Fail closed if entity_platform_status is missing critical columns."""
    rows = db.fetchall("PRAGMA table_info(entity_platform_status)")
    names = {str(r["name"] if isinstance(r, dict) else r[1]) for r in (rows or [])}
    missing = [c for c in _CRITICAL_EPS_COLS if c not in names]
    if missing:
        raise RuntimeError(f"schema incomplete, missing EPS columns: {missing}")
