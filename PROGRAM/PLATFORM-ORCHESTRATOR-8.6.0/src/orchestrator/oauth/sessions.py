"""oauth_sessions persistence (SQLite, additive).

Table shape (C2 / C5):
  id, provider, state_hash, code_verifier, account_hint,
  created_at, expires_at, consumed_at, redirect_uri
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)

SESSION_TTL_SEC = 600  # 10 minutes


class _DB(Protocol):
    def execute(self, sql: str, params: tuple | list = ()) -> Any: ...
    def fetchone(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None: ...
    def fetchall(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]: ...


@dataclass
class OAuthSession:
    id: str
    provider: str
    state_hash: str
    code_verifier: str
    account_hint: str = ""
    created_at: float = 0.0
    expires_at: float = 0.0
    consumed_at: float | None = None
    redirect_uri: str = ""
    claimed_at: float | None = None
    claim_token: str = ""

    @property
    def expired(self) -> bool:
        return time.time() >= float(self.expires_at or 0)

    @property
    def consumed(self) -> bool:
        return self.consumed_at is not None and float(self.consumed_at) > 0

    @property
    def processing(self) -> bool:
        return self.claimed_at is not None and float(self.claimed_at) > 0 and not self.consumed


def hash_state(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def new_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge S256)."""
    import base64
    import hashlib as _hl

    verifier = secrets.token_urlsafe(64)[:128]
    digest = _hl.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def new_state() -> str:
    return secrets.token_urlsafe(32)


class OAuthSessionStore:
    """CRUD for oauth_sessions. Requires table created by DB migration."""

    def __init__(self, db: _DB) -> None:
        self._db = db

    def create(
        self,
        *,
        provider: str,
        code_verifier: str,
        state: str,
        redirect_uri: str,
        account_hint: str = "",
        ttl_sec: float = SESSION_TTL_SEC,
    ) -> OAuthSession:
        now = time.time()
        sid = secrets.token_urlsafe(16)
        sh = hash_state(state)
        sess = OAuthSession(
            id=sid,
            provider=provider.strip().lower(),
            state_hash=sh,
            code_verifier=code_verifier,
            account_hint=account_hint or "",
            created_at=now,
            expires_at=now + float(ttl_sec),
            consumed_at=None,
            redirect_uri=redirect_uri,
        )
        if self._supports_claiming():
            self._db.execute(
                """
                INSERT INTO oauth_sessions
                    (id, provider, state_hash, code_verifier, account_hint,
                     created_at, expires_at, consumed_at, claimed_at, claim_token, redirect_uri)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?)
                """,
                (
                    sess.id, sess.provider, sess.state_hash, sess.code_verifier,
                    sess.account_hint, sess.created_at, sess.expires_at, sess.redirect_uri,
                ),
            )
        else:
            # Compatibility for old lightweight test stores / pre-v21 DB wrappers.
            self._db.execute(
                """
                INSERT INTO oauth_sessions
                    (id, provider, state_hash, code_verifier, account_hint,
                     created_at, expires_at, consumed_at, redirect_uri)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    sess.id, sess.provider, sess.state_hash, sess.code_verifier,
                    sess.account_hint, sess.created_at, sess.expires_at, sess.redirect_uri,
                ),
            )
        return sess

    def get_by_state(self, state: str) -> OAuthSession | None:
        sh = hash_state(state)
        row = self._db.fetchone(
            "SELECT * FROM oauth_sessions WHERE state_hash=? ORDER BY created_at DESC LIMIT 1",
            (sh,),
        )
        return self._row_to_session(row) if row else None

    def get(self, session_id: str) -> OAuthSession | None:
        row = self._db.fetchone(
            "SELECT * FROM oauth_sessions WHERE id=?", (session_id,),
        )
        return self._row_to_session(row) if row else None

    def _supports_claiming(self) -> bool:
        try:
            rows = self._db.fetchall("PRAGMA table_info(oauth_sessions)")
            return "claimed_at" in {str(r.get("name") if isinstance(r, dict) else r[1]) for r in rows}
        except Exception:
            return False

    def claim(self, session_id: str) -> bool:
        """Atomically claim a callback; modern DBs use a unique claim token."""
        if not self._supports_claiming():
            row = self._db.fetchone("SELECT consumed_at FROM oauth_sessions WHERE id=?", (session_id,))
            return bool(row is not None and not row.get("consumed_at"))
        token = secrets.token_urlsafe(18)
        now = time.time()
        try:
            self._db.execute(
                "UPDATE oauth_sessions SET claimed_at=?, claim_token=? WHERE id=? "
                "AND consumed_at IS NULL AND claimed_at IS NULL AND expires_at>=?",
                (now, token, session_id, time.time()),
            )
            row = self._db.fetchone("SELECT claim_token FROM oauth_sessions WHERE id=?", (session_id,))
            # Verify ownership, not sqlite cursor.rowcount (which can be driver-sensitive).
            self._claim_token = token
            return bool(row and str(row.get("claim_token") or "") == token)
        except Exception:
            logger.debug("oauth session claim failed", exc_info=True)
            return False

    def release_claim(self, session_id: str) -> None:
        if not self._supports_claiming():
            return
        self._db.execute(
            "UPDATE oauth_sessions SET claimed_at=NULL, claim_token=NULL WHERE id=? AND consumed_at IS NULL",
            (session_id,),
        )

    def mark_consumed(self, session_id: str) -> None:
        if self._supports_claiming():
            self._db.execute(
                "UPDATE oauth_sessions SET consumed_at=?, claimed_at=NULL, claim_token=NULL WHERE id=?",
                (time.time(), session_id),
            )
        else:
            self._db.execute(
                "UPDATE oauth_sessions SET consumed_at=? WHERE id=?",
                (time.time(), session_id),
            )

    def cleanup_expired(self, *, older_than_sec: float = 86400) -> int:
        cutoff = time.time() - float(older_than_sec)
        # delete expired or long-consumed
        self._db.execute(
            "DELETE FROM oauth_sessions WHERE expires_at < ? OR "
            "(consumed_at IS NOT NULL AND consumed_at < ?)",
            (time.time(), cutoff),
        )
        return 0

    @staticmethod
    def _row_to_session(row: dict[str, Any]) -> OAuthSession:
        return OAuthSession(
            id=str(row["id"]),
            provider=str(row["provider"]),
            state_hash=str(row["state_hash"]),
            code_verifier=str(row["code_verifier"]),
            account_hint=str(row.get("account_hint") or ""),
            created_at=float(row.get("created_at") or 0),
            expires_at=float(row.get("expires_at") or 0),
            consumed_at=(float(row["consumed_at"]) if row.get("consumed_at") else None),
            redirect_uri=str(row.get("redirect_uri") or ""),
            claimed_at=(float(row["claimed_at"]) if row.get("claimed_at") else None),
            claim_token=str(row.get("claim_token") or ""),
        )
