"""Web-facing OAuth handlers kept outside the WebAppAPI monolith."""
from __future__ import annotations

import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _public_base_url() -> str:
    return os.getenv("ORCH_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def _providers() -> dict[str, Any]:
    from .manager import FACEBOOK, GOOGLE_YOUTUBE, INSTAGRAM, THREADS, TIKTOK

    return {
        "youtube": GOOGLE_YOUTUBE,
        "facebook": FACEBOOK,
        "instagram": INSTAGRAM,
        "threads": THREADS,
        "tiktok": TIKTOK,
    }


def _account_store(db: Any) -> Any:
    try:
        from ..accounts.store import PlatformAccountStore
        return PlatformAccountStore(db)
    except Exception:
        logger.debug("OAuth account store unavailable", exc_info=True)
        return None


def start(
    db: Any,
    provider: str,
    *,
    token_saver: Callable[[str, Any, str], None],
    account_hint: str = "",
) -> dict[str, Any]:
    """Build an OAuth authorization URL and persist its CSRF/PKCE session."""
    try:
        from .manager import OAuthManager
        from .sessions import OAuthSessionStore

        mgr = OAuthManager(
            public_base_url=_public_base_url(),
            session_store=OAuthSessionStore(db),
            providers=_providers(),
            account_store=_account_store(db),
            token_saver=token_saver,
        )
        result = mgr.start(provider, account_hint=account_hint)
        return {
            "authorize_url": result.authorize_url,
            "state": result.state,
            "session_id": result.session_id,
        }
    except Exception as exc:
        return {"error": str(exc)}


def callback(
    db: Any,
    provider: str,
    params: dict[str, Any],
    *,
    token_saver: Callable[[str, Any, str], None],
) -> dict[str, Any]:
    """Exchange the OAuth code after state validation and save the resulting token."""
    try:
        from .manager import OAuthManager
        from .sessions import OAuthSessionStore

        mgr = OAuthManager(
            public_base_url=_public_base_url(),
            session_store=OAuthSessionStore(db),
            providers=_providers(),
            account_store=_account_store(db),
            token_saver=token_saver,
        )
        code = str(params.get("code") or "")
        state = str(params.get("state") or "")
        result = mgr.handle_callback(provider, code=code, state=state)
        return {"ok": True, "provider": provider, "expires_in": result.expires_in}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
