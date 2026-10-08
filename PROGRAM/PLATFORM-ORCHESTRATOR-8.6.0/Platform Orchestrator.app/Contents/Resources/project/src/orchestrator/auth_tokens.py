"""Unified account-scoped access-token resolution for provider modules."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TokenResolutionError(RuntimeError):
    """Raised when a configured token broker cannot be used in strict mode."""


def _broker_client():
    from .engines.token_broker_client import TokenBrokerClient

    url = os.getenv("TOKEN_BROKER_URL", "").strip()
    if not url:
        return None
    secret = os.getenv("TOKEN_BROKER_SECRET", "")
    return TokenBrokerClient(url, secret)


def get_access_token(platform: str, account_id: str = "") -> str:
    """Resolve token: configured broker → account-scoped file → legacy shared file.

    When TOKEN_BROKER_URL is configured, a broker error is observable in strict mode
    (TOKEN_BROKER_STRICT=1); otherwise the documented local-file fallback remains
    available for single-host operation.
    """
    plat = (platform or "").strip().lower()
    aid = (account_id or "").strip()
    if not plat:
        return ""

    broker = _broker_client()
    if broker is not None:
        strict = os.getenv("TOKEN_BROKER_STRICT", "1").strip().lower() in {"1", "true", "yes", "on"}
        try:
            data = broker.get(plat, aid or None)
            tok = str((data or {}).get("token") or (data or {}).get("access_token") or "")
            if tok:
                return tok
            if strict:
                raise TokenResolutionError(f"token broker returned no token for {plat}/{aid or '*'}")
        except Exception as exc:
            if strict:
                raise TokenResolutionError(f"token broker failed for {plat}/{aid or '*'}: {exc}") from exc
            logger.warning("token broker unavailable for %s: %s; using local token store", plat, type(exc).__name__)

    root = Path(os.getenv("TOKENS_DIR", "tokens"))
    # Account-scoped lifecycle records take precedence and enforce revoked/quarantine/expiry.
    if aid:
        try:
            from .token_lifecycle import TokenLifecycleStore
            rec = TokenLifecycleStore(root).load(plat, aid)
            if rec is not None:
                if not rec.usable():
                    return ""
                if rec.access_token:
                    return rec.access_token
        except Exception:
            logger.debug("token lifecycle read failed", exc_info=True)
    candidates: list[Path] = []
    if aid:
        candidates.append(root / f"{plat}__{aid}.json")
        # Never cross-account fall back to a shared provider token unless explicitly enabled.
        allow_shared = os.getenv("TOKEN_ALLOW_SHARED_FALLBACK", "0").strip().lower() in {"1", "true", "yes", "on"}
        if allow_shared:
            candidates.append(root / f"{plat}.json")
    else:
        candidates.append(root / f"{plat}.json")
    for path in candidates:
        if not path.is_file():
            continue
        try:
            try:
                os.chmod(path, 0o600)
            except OSError as exc:
                logger.debug("token chmod failed: %s", type(exc).__name__)
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            tok = str(data.get("access_token") or data.get("token") or "")
            if tok:
                return tok
        except Exception:
            logger.debug("auth_tokens read failed %s", path, exc_info=True)
    return ""


def token_provider_for(platform_hint: str = ""):
    """Return callable compatible with module registry token_provider(plat, account_id)."""

    def _provider(plat: str, account_id: str = "") -> str:
        return get_access_token(plat or platform_hint, account_id=account_id)

    return _provider
