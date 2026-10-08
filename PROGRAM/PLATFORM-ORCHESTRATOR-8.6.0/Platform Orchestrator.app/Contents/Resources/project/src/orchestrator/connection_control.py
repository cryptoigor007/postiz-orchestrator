from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ConnectionChecklist:
    provider: str
    account_id: str
    auth_method: str
    auth_strategy: str
    token_present: bool
    token_usable: bool
    account_enabled: bool
    connection_state: str
    ready: bool
    blockers: list[str]


class ConnectionControl:
    """Unified provider connection onboarding/reconnect/disconnect control plane."""

    def __init__(self, db: Any, registry: Any, token_lifecycle: Any, account_store: Any):
        self.db = db
        self.registry = registry
        self.tokens = token_lifecycle
        self.accounts = account_store

    def checklist(self, provider: str, account_id: str) -> ConnectionChecklist:
        provider = provider.strip().lower()
        mod = self.registry.create(provider) if self.registry and self.registry.has(provider) else None
        manifest = getattr(mod, "manifest", None)
        auth = getattr(manifest, "auth", {}) or {}
        method = str(auth.get("method") or "planned")
        strategy = str(auth.get("strategy") or "")
        acc = self.accounts.get(account_id) if self.accounts else None
        rec = self.tokens.load(provider, account_id) if self.tokens and account_id else None
        token_present = bool(rec and rec.access_token)
        token_usable = bool(rec and rec.usable())
        enabled = bool(acc.enabled) if acc else False
        state = str(acc.connection_state if acc else "NOT_CONFIGURED")
        blockers: list[str] = []
        if method in {"oauth", "oauth2_authorization_code"} and not strategy:
            blockers.append("missing_auth_strategy")
        if not token_present:
            blockers.append("token_missing")
        elif not token_usable:
            blockers.append("token_unusable")
        if acc is None:
            blockers.append("account_missing")
        elif not enabled:
            blockers.append("account_disabled")
        return ConnectionChecklist(provider, account_id, method, strategy, token_present, token_usable, enabled, state, not blockers, blockers)

    def disconnect(self, account_id: str, *, reason: str = "manual_disconnect") -> bool:
        acc = self.accounts.get(account_id)
        if not acc:
            return False
        self.tokens.revoke(acc.platform, account_id, reason=reason)
        self.accounts.set_enabled(account_id, False)
        self.db.execute(
            "UPDATE platform_accounts SET connection_state='DISCONNECTED', refresh_status='revoked', updated_at=? WHERE id=?",
            (__import__('time').time(), account_id),
        )
        return True

    def mark_authorizing(self, account_id: str) -> bool:
        return bool(self.db.execute(
            "UPDATE platform_accounts SET connection_state='AUTHORIZING', updated_at=? WHERE id=?",
            (__import__('time').time(), account_id),
        ))

    def mark_connected(self, account_id: str, *, expires_at: float | None = None, scopes: str = "") -> bool:
        return bool(self.db.execute(
            "UPDATE platform_accounts SET connection_state='CONNECTED', enabled=1, expires_at=?, granted_scopes=?, updated_at=? WHERE id=?",
            (expires_at, scopes, __import__('time').time(), account_id),
        ))

    @staticmethod
    def as_dict(checklist: ConnectionChecklist) -> dict[str, Any]:
        return asdict(checklist)
