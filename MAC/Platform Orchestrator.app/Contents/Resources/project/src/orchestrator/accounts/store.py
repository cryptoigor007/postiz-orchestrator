"""platform_accounts CRUD with account-aware connection metadata."""
from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class _DB(Protocol):
    def execute(self, sql: str, params: tuple | list = ()) -> Any: ...
    def fetchone(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None: ...
    def fetchall(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]: ...


@dataclass
class PlatformAccount:
    id: str
    platform: str
    external_account_id: str = ""
    name: str = ""
    username: str = ""
    project_id: str = ""
    enabled: bool = True
    auth_provider: str = ""
    token_ref: str = ""
    connection_state: str = "NOT_CONFIGURED"
    granted_scopes: str = ""
    expires_at: float | None = None
    refresh_status: str = "unknown"
    webhook_status: str = "unknown"
    review_state: str = "unknown"
    app_id: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0


class PlatformAccountStore:
    def __init__(self, db: _DB) -> None:
        self._db = db

    def _columns(self) -> set[str]:
        try:
            rows = self._db.fetchall("PRAGMA table_info(platform_accounts)")
            return {str(r.get("name") if isinstance(r, dict) else r[1]) for r in rows}
        except Exception:
            return set()

    def upsert(
        self,
        *,
        platform: str,
        external_account_id: str = "",
        name: str = "",
        username: str = "",
        project_id: str = "",
        enabled: bool = True,
        auth_provider: str = "",
        token_ref: str = "",
        connection_state: str = "NOT_CONFIGURED",
        granted_scopes: str = "",
        expires_at: float | None = None,
        refresh_status: str = "unknown",
        webhook_status: str = "unknown",
        review_state: str = "unknown",
        app_id: str = "",
        account_id: str | None = None,
    ) -> PlatformAccount:
        now = time.time()
        platform = platform.strip().lower()
        cols = self._columns()
        modern = {"connection_state", "granted_scopes", "expires_at", "refresh_status", "webhook_status", "review_state", "app_id"} <= cols
        existing = None
        if external_account_id:
            existing = self._db.fetchone(
                "SELECT * FROM platform_accounts WHERE platform=? AND external_account_id=?",
                (platform, external_account_id),
            )
        if existing:
            aid = str(existing["id"])
            fields: dict[str, Any] = {
                "name": name or existing.get("name") or "",
                "username": username or existing.get("username") or "",
                "project_id": project_id or existing.get("project_id") or "",
                "enabled": 1 if enabled else 0,
                "auth_provider": auth_provider or existing.get("auth_provider") or "",
                "token_ref": token_ref or existing.get("token_ref") or "",
            }
            if modern:
                fields.update({
                    "connection_state": connection_state or existing.get("connection_state") or "NOT_CONFIGURED",
                    "granted_scopes": granted_scopes or existing.get("granted_scopes") or "",
                    "expires_at": expires_at if expires_at is not None else existing.get("expires_at"),
                    "refresh_status": refresh_status or existing.get("refresh_status") or "unknown",
                    "webhook_status": webhook_status or existing.get("webhook_status") or "unknown",
                    "review_state": review_state or existing.get("review_state") or "unknown",
                    "app_id": app_id or existing.get("app_id") or "",
                })
            sets = [f"{k}=?" for k in fields]
            params = list(fields.values()) + [now, aid]
            sets.append("updated_at=?")
            self._db.execute(f"UPDATE platform_accounts SET {', '.join(sets)} WHERE id=?", tuple(params))
            return self.get(aid)  # type: ignore[return-value]

        aid = account_id or secrets.token_urlsafe(12)
        base_cols = [
            "id", "platform", "external_account_id", "name", "username", "project_id",
            "enabled", "auth_provider", "token_ref", "created_at", "updated_at",
        ]
        vals: list[Any] = [
            aid, platform, external_account_id, name, username, project_id,
            1 if enabled else 0, auth_provider, token_ref, now, now,
        ]
        if modern:
            # Insert extended columns immediately before timestamps.
            idx = base_cols.index("created_at")
            extra_cols = ["connection_state", "granted_scopes", "expires_at", "refresh_status", "webhook_status", "review_state", "app_id"]
            base_cols[idx:idx] = extra_cols
            vals[idx:idx] = [connection_state, granted_scopes, expires_at, refresh_status, webhook_status, review_state, app_id]
        placeholders = ", ".join("?" for _ in base_cols)
        self._db.execute(
            f"INSERT INTO platform_accounts ({', '.join(base_cols)}) VALUES ({placeholders})",
            tuple(vals),
        )
        return self.get(aid) or PlatformAccount(
            id=aid, platform=platform, external_account_id=external_account_id,
            name=name, username=username, project_id=project_id, enabled=enabled,
            auth_provider=auth_provider, token_ref=token_ref,
            connection_state=connection_state, granted_scopes=granted_scopes,
            expires_at=expires_at, refresh_status=refresh_status,
            webhook_status=webhook_status, review_state=review_state, app_id=app_id,
            created_at=now, updated_at=now,
        )

    def get(self, account_id: str) -> PlatformAccount | None:
        row = self._db.fetchone("SELECT * FROM platform_accounts WHERE id=?", (account_id,))
        return self._from_row(row) if row else None

    def list(
        self,
        *,
        platform: str | None = None,
        project_id: str | None = None,
        enabled_only: bool = False,
    ) -> list[PlatformAccount]:
        sql = "SELECT * FROM platform_accounts WHERE 1=1"
        params: list[Any] = []
        if platform:
            sql += " AND platform=?"
            params.append(platform.strip().lower())
        if project_id is not None:
            sql += " AND project_id=?"
            params.append(project_id)
        if enabled_only:
            sql += " AND enabled=1"
        sql += " ORDER BY platform, name"
        rows = self._db.fetchall(sql, tuple(params))
        return [self._from_row(r) for r in rows]

    def set_enabled(self, account_id: str, enabled: bool) -> None:
        self._db.execute(
            "UPDATE platform_accounts SET enabled=?, updated_at=? WHERE id=?",
            (1 if enabled else 0, time.time(), account_id),
        )

    @staticmethod
    def _from_row(row: dict[str, Any]) -> PlatformAccount:
        return PlatformAccount(
            id=str(row["id"]),
            platform=str(row["platform"]),
            external_account_id=str(row.get("external_account_id") or ""),
            name=str(row.get("name") or ""),
            username=str(row.get("username") or ""),
            project_id=str(row.get("project_id") or ""),
            enabled=bool(row.get("enabled", 1)),
            auth_provider=str(row.get("auth_provider") or ""),
            token_ref=str(row.get("token_ref") or ""),
            connection_state=str(row.get("connection_state") or "NOT_CONFIGURED"),
            granted_scopes=str(row.get("granted_scopes") or ""),
            expires_at=(float(row["expires_at"]) if row.get("expires_at") is not None else None),
            refresh_status=str(row.get("refresh_status") or "unknown"),
            webhook_status=str(row.get("webhook_status") or "unknown"),
            review_state=str(row.get("review_state") or "unknown"),
            app_id=str(row.get("app_id") or ""),
            created_at=float(row.get("created_at") or 0),
            updated_at=float(row.get("updated_at") or 0),
        )
