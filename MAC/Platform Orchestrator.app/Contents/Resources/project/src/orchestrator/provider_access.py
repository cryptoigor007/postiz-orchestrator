"""Provider connection/access-state model and persistence helpers."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import time
from typing import Any


STATES = (
    "NOT_CONFIGURED", "DEV_CONNECTED", "AUTHORIZING", "CONNECTED", "TOKEN_EXPIRED",
    "SCOPES_MISSING", "BUSINESS_VERIFICATION_REQUIRED", "APP_REVIEW_REQUIRED",
    "ADVANCED_ACCESS_REQUIRED", "AUDIT_REQUIRED", "LIVE", "PARTNER_REQUIRED",
    "MANUAL_ONLY", "DISABLED", "DISCONNECTED", "DEGRADED",
)


@dataclass(frozen=True)
class ProviderAccessSnapshot:
    provider: str
    account_id: str = ""
    credentials_ok: bool = False
    redirect_ok: bool = False
    account_ok: bool = False
    token_ok: bool = False
    scopes_ok: bool = False
    business_verification_ok: bool = False
    app_review_ok: bool = False
    audit_ok: bool = False
    webhook_ok: bool = False
    media_host_ok: bool = True
    smoke_test_ok: bool = False
    live_ok: bool = False
    state: str = "NOT_CONFIGURED"
    details: str = ""

    def validate(self) -> None:
        if self.state not in STATES:
            raise ValueError(f"unknown provider access state: {self.state}")


class ProviderAccessStore:
    def __init__(self, db: Any):
        self.db = db

    def upsert(self, snapshot: ProviderAccessSnapshot) -> None:
        snapshot.validate()
        now = time.time()
        self.db.execute(
            """INSERT INTO provider_access
            (platform, account_id, state, credentials_ok, redirect_ok, account_ok,
             token_ok, scopes_ok, business_verification_ok, app_review_ok, audit_ok,
             webhook_ok, media_host_ok, smoke_test_ok, live_ok, details, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, account_id) DO UPDATE SET
              state=excluded.state, credentials_ok=excluded.credentials_ok,
              redirect_ok=excluded.redirect_ok, account_ok=excluded.account_ok,
              token_ok=excluded.token_ok, scopes_ok=excluded.scopes_ok,
              business_verification_ok=excluded.business_verification_ok,
              app_review_ok=excluded.app_review_ok, audit_ok=excluded.audit_ok,
              webhook_ok=excluded.webhook_ok, media_host_ok=excluded.media_host_ok,
              smoke_test_ok=excluded.smoke_test_ok, live_ok=excluded.live_ok,
              details=excluded.details, updated_at=excluded.updated_at""",
            (
                snapshot.provider.lower(), snapshot.account_id, snapshot.state,
                int(snapshot.credentials_ok), int(snapshot.redirect_ok), int(snapshot.account_ok),
                int(snapshot.token_ok), int(snapshot.scopes_ok), int(snapshot.business_verification_ok),
                int(snapshot.app_review_ok), int(snapshot.audit_ok), int(snapshot.webhook_ok),
                int(snapshot.media_host_ok), int(snapshot.smoke_test_ok), int(snapshot.live_ok),
                snapshot.details[:2000], now,
            ),
        )

    def get(self, provider: str, account_id: str = "") -> ProviderAccessSnapshot | None:
        row = self.db.fetchone(
            "SELECT * FROM provider_access WHERE platform=? AND account_id=?",
            (provider.lower(), account_id),
        )
        if not row:
            return None
        return ProviderAccessSnapshot(
            provider=str(row.get("platform") or provider), account_id=str(row.get("account_id") or ""),
            credentials_ok=bool(row.get("credentials_ok")), redirect_ok=bool(row.get("redirect_ok")),
            account_ok=bool(row.get("account_ok")), token_ok=bool(row.get("token_ok")),
            scopes_ok=bool(row.get("scopes_ok")), business_verification_ok=bool(row.get("business_verification_ok")),
            app_review_ok=bool(row.get("app_review_ok")), audit_ok=bool(row.get("audit_ok")),
            webhook_ok=bool(row.get("webhook_ok")), media_host_ok=bool(row.get("media_host_ok")),
            smoke_test_ok=bool(row.get("smoke_test_ok")), live_ok=bool(row.get("live_ok")),
            state=str(row.get("state") or "NOT_CONFIGURED"), details=str(row.get("details") or ""),
        )

    def snapshot_all(self) -> dict[str, dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM provider_access ORDER BY platform, account_id"
        )
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            snap = self.get(str(row.get("platform") or ""), str(row.get("account_id") or ""))
            if snap is None:
                continue
            item = asdict(snap)
            out[f"{snap.provider}::{snap.account_id}"] = item
        return out
