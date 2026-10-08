from __future__ import annotations

import json
import logging
import os
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TokenRecord:
    platform: str
    account_id: str
    access_token: str
    refresh_token: str = ""
    expires_at: float | None = None
    revoked: bool = False
    quarantined: bool = False
    version: int = 1
    metadata: dict[str, Any] | None = None

    def usable(self, *, now: float | None = None) -> bool:
        if self.revoked or self.quarantined or not self.access_token:
            return False
        now = time.time() if now is None else float(now)
        return self.expires_at is None or self.expires_at > now + 30


class TokenLifecycleStore:
    """Account-scoped token persistence and lifecycle state."""

    def __init__(self, root: str | Path = "tokens", db: Any = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = db

    def path(self, platform: str, account_id: str) -> Path:
        if not account_id:
            raise ValueError("account_id is required for lifecycle storage")
        safe_platform = quote(str(platform).strip().lower(), safe="")
        safe_account = quote(str(account_id).strip(), safe="")
        path = self.root / f"{safe_platform}__{safe_account}.json"
        # account_id is externally supplied by the OAuth start request; keep
        # lifecycle files physically inside TOKENS_DIR even for hostile input.
        root = self.root.resolve()
        resolved_parent = path.parent.resolve()
        if resolved_parent != root:
            raise ValueError("invalid token lifecycle path")
        return path

    def load(self, platform: str, account_id: str) -> TokenRecord | None:
        p = self.path(platform, account_id)
        if not p.is_file():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            rec = TokenRecord(
                platform=platform.strip().lower(), account_id=account_id,
                access_token=str(data.get("access_token") or data.get("token") or ""),
                refresh_token=str(data.get("refresh_token") or ""),
                expires_at=float(data["expires_at"]) if data.get("expires_at") is not None else None,
                revoked=bool(data.get("revoked", False)),
                quarantined=bool(data.get("quarantined", False)),
                version=int(data.get("version") or 1),
                metadata=dict(data.get("metadata") or {}),
            )
            return rec
        except Exception:
            return None

    def save(self, rec: TokenRecord) -> None:
        p = self.path(rec.platform, rec.account_id)
        payload = {
            "version": int(rec.version),
            "access_token": rec.access_token,
            "refresh_token": rec.refresh_token,
            "expires_at": rec.expires_at,
            "revoked": bool(rec.revoked),
            "quarantined": bool(rec.quarantined),
            "metadata": rec.metadata or {},
            "updated_at": time.time(),
        }
        fd, tmp = tempfile.mkstemp(prefix=f".{p.name}.", dir=str(p.parent))
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, sort_keys=True)
                fh.flush(); os.fsync(fh.fileno())
            os.replace(tmp, p)
        finally:
            try: os.unlink(tmp)
            except OSError as exc: logger.debug("token temp cleanup failed: %s", type(exc).__name__)
        self._sync_account(rec)

    def rotate(self, platform: str, account_id: str, *, access_token: str,
               refresh_token: str = "", expires_at: float | None = None, metadata: dict[str, Any] | None = None) -> TokenRecord:
        old = self.load(platform, account_id)
        rec = TokenRecord(
            platform=platform.strip().lower(), account_id=account_id,
            access_token=access_token, refresh_token=refresh_token,
            expires_at=expires_at, revoked=False, quarantined=False,
            version=(old.version + 1 if old else 1), metadata=metadata or (old.metadata if old else {}),
        )
        self.save(rec)
        return rec

    def refresh_expiring(self, platform: str, account_id: str, *, skew_sec: float = 600.0) -> str:
        """Refresh an account-scoped OAuth token when it is inside the refresh window.

        Returns one of: not_due, refreshed, skipped, unsupported, failed:<type>.
        The provider-specific token stores update the same account file atomically.
        """
        import time as _time
        from .platforms.token_store import make_meta_token_store, make_tiktok_token_store
        platform = str(platform or "").strip().lower()
        account_id = str(account_id or "").strip()
        if not account_id:
            return "skipped"
        rec = self.load(platform, account_id)
        meta_exchange = platform in {"facebook", "instagram", "threads"}
        if rec is None or ((not rec.refresh_token) and not meta_exchange) or not rec.access_token or rec.expires_at is None:
            return "skipped"
        if float(rec.expires_at) > _time.time() + max(60.0, float(skew_sec)):
            return "not_due"
        path = self.path(platform, account_id)
        try:
            if platform == "youtube":
                from .platforms.youtube.token_store import YouTubeTokenStore
                store = YouTubeTokenStore(
                    path,
                    client_id=os.getenv("YT_CLIENT_ID", ""),
                    client_secret=os.getenv("YT_CLIENT_SECRET", ""),
                )
            elif platform in {"facebook", "instagram", "threads"}:
                store = make_meta_token_store(platform, tokens_path=path)
            elif platform == "tiktok":
                store = make_tiktok_token_store(tokens_path=path)
            else:
                return "unsupported"
            store.get_access_token()
            refreshed = self.load(platform, account_id)
            if refreshed is not None:
                self._sync_account(refreshed)
            return "refreshed"
        except Exception as exc:
            self._sync_account(rec)
            return f"failed:{type(exc).__name__}"

    def revoke(self, platform: str, account_id: str, *, reason: str = "revoked") -> bool:
        rec = self.load(platform, account_id)
        if rec is None:
            return False
        rec.revoked = True
        rec.quarantined = False
        rec.metadata = {**(rec.metadata or {}), "revoke_reason": reason, "revoked_at": time.time()}
        self.save(rec)
        return True

    def quarantine(self, platform: str, account_id: str, *, reason: str = "quarantined") -> bool:
        rec = self.load(platform, account_id)
        if rec is None:
            return False
        rec.quarantined = True
        rec.metadata = {**(rec.metadata or {}), "quarantine_reason": reason, "quarantined_at": time.time()}
        self.save(rec)
        return True

    def _sync_account(self, rec: TokenRecord) -> None:
        if self.db is None:
            return
        state = "TOKEN_EXPIRED" if (rec.expires_at is not None and not rec.usable()) else "CONNECTED"
        if rec.revoked:
            state = "DISCONNECTED"
        elif rec.quarantined:
            state = "DEGRADED"
        self.db.execute(
            "UPDATE platform_accounts SET token_ref=?, expires_at=?, refresh_status=?, connection_state=?, updated_at=? WHERE id=?",
            (str(self.path(rec.platform, rec.account_id)), rec.expires_at,
             "available" if rec.refresh_token else "none", state, time.time(), rec.account_id),
        )
