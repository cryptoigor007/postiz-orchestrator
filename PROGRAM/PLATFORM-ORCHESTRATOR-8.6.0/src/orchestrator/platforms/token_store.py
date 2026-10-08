"""Общий шаблон OAuth token store (как youtube/token_store.py).

Для Meta (Instagram/Facebook/Threads) и TikTok — без live-ключей.
Файлы: tokens/<platform>.json (права 600). Секреты только из env.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ..http_client import ModuleHttpClient, mask_secrets
from .base import ModuleError, ModuleErrorCode

logger = logging.getLogger(__name__)
REFRESH_SKEW_SEC = 600
NO_EXPIRY_POLICY_TTL_SEC = 3600
META_TOKEN_URL = "https://graph.facebook.com/v26.0/oauth/access_token"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


@dataclass
class TokenData:
    access_token: str
    refresh_token: str = ""
    expires_at: float = 0.0
    token_type: str = "Bearer"
    scope: str = ""
    extra: dict[str, Any] | None = None
    # When True, expires_at<=0 is treated as non-expiring (explicit opt-in only).
    no_expiry: bool = False

    def access_valid(self, skew: float = REFRESH_SKEW_SEC) -> bool:
        if not self.access_token:
            return False
        if self.expires_at <= 0:
            if self.no_expiry:
                return True
            # Fail-closed (C1): unknown/zero expiry is NOT forever-valid.
            return False
        return time.time() < (self.expires_at - skew)


class OAuthTokenStore:
    def __init__(
        self,
        platform: str,
        path: str | Path,
        *,
        token_url: str = "",
        client_id: str = "",
        client_secret: str = "",
        http: ModuleHttpClient | None = None,
        skew_sec: float = REFRESH_SKEW_SEC,
        refresh_grant_type: str = "refresh_token",
        refresh_token_param: str = "refresh_token",
        extra_refresh_params: dict[str, str] | None = None,
        no_expiry_policy_ttl: float = NO_EXPIRY_POLICY_TTL_SEC,
    ) -> None:
        self.platform = str(platform or "unknown").strip().lower()
        self.path = Path(path)
        self.token_url = (token_url or "").strip()
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self.skew_sec = skew_sec
        self.refresh_grant_type = refresh_grant_type
        self.refresh_token_param = str(refresh_token_param or "refresh_token")
        self.extra_refresh_params = dict(extra_refresh_params or {})
        self.no_expiry_policy_ttl = float(no_expiry_policy_ttl)
        self._http = http or ModuleHttpClient(
            platform=self.platform, module_version="0.2.0", max_retries=3,
        )
        self._cache: TokenData | None = None

    def load(self) -> TokenData | None:
        if not self.path.is_file():
            self._cache = None
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("%s token_store: cannot read %s", self.platform, self.path)
            return None
        if not isinstance(raw, dict):
            return None
        no_expiry = bool(raw.get("no_expiry") or False)
        expires_at = float(raw.get("expires_at") or 0)
        # Policy TTL: if no absolute expiry, derive from updated_at + TTL.
        if expires_at <= 0 and not no_expiry:
            updated_at = float(raw.get("updated_at") or 0)
            ttl = float(getattr(self, "no_expiry_policy_ttl", 3600) or 3600)
            if updated_at > 0 and ttl > 0:
                expires_at = updated_at + ttl
        skip = {
            "access_token", "refresh_token", "expires_at", "token_type",
            "scope", "no_expiry", "updated_at",
        }
        td = TokenData(
            access_token=str(raw.get("access_token") or ""),
            refresh_token=str(raw.get("refresh_token") or ""),
            expires_at=expires_at,
            token_type=str(raw.get("token_type") or "Bearer"),
            scope=str(raw.get("scope") or ""),
            no_expiry=no_expiry,
            extra={k: v for k, v in raw.items() if k not in skip},
        )
        self._cache = td
        return td

    def save(self, td: TokenData) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError as exc:
            logger.debug("token directory chmod failed: %s", type(exc).__name__)
        payload: dict[str, Any] = {
            "access_token": td.access_token,
            "refresh_token": td.refresh_token,
            "expires_at": td.expires_at,
            "token_type": td.token_type,
            "scope": td.scope,
            "updated_at": time.time(),
        }
        if td.no_expiry:
            payload["no_expiry"] = True
        if td.extra:
            payload.update(td.extra)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError as exc:
            logger.debug("token directory chmod failed: %s", type(exc).__name__)
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError as exc:
            logger.debug("token directory chmod failed: %s", type(exc).__name__)
        self._cache = td

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        """Return valid access_token or raise AUTH_REQUIRED (fail-closed C1)."""
        td = self._cache or self.load()
        if td is None or not td.access_token:
            return ""
        if not force_refresh and td.access_valid(self.skew_sec):
            return td.access_token
        # Expired / force — must refresh; never return stale token.
        if (not td.refresh_token and self.refresh_token_param != "fb_exchange_token") or not self.token_url:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"{self.platform}: access token expired and no refresh credential/token_url",
                action="повторный OAuth у владельца",
            )
        return self._refresh(td)

    def _refresh(self, td: TokenData) -> str:
        if not self.client_id or not self.client_secret:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"{self.platform}: token refresh requires client_id/client_secret",
                action="задайте client_id/secret в env (mode 600)",
            )
        refresh_value = td.access_token if self.refresh_token_param == "fb_exchange_token" else td.refresh_token
        body = {
            "grant_type": self.refresh_grant_type,
            self.refresh_token_param: refresh_value,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        body.update(self.extra_refresh_params)
        try:
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            encoded = urlencode(body).encode("utf-8")
            resp = self._http.request(
                "POST", self.token_url, headers=headers, content=encoded, idempotent=True,
            )
            if resp.status_code >= 400:
                text = mask_secrets(resp.text[:500] if resp.text else "")
                if "invalid_grant" in text.lower() or resp.status_code in (400, 401):
                    raise ModuleError(
                        ModuleErrorCode.AUTH_REQUIRED,
                        f"{self.platform}: refresh invalid_grant",
                        action="повторный OAuth у владельца",
                    )
                raise ModuleError(
                    ModuleErrorCode.TRANSIENT,
                    f"{self.platform}: token refresh HTTP {resp.status_code}",
                    action="повторить позже",
                )
            data = resp.json() if resp.content else {}
        except ModuleError:
            raise
        except Exception as e:
            raise ModuleError(
                ModuleErrorCode.TRANSIENT,
                f"{self.platform}: token refresh failed: {e}",
                action="повторить позже",
            ) from e
        new_access = str(data.get("access_token") or "")
        if not new_access:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"{self.platform}: refresh без access_token",
                action="повторный OAuth",
            )
        expires_in = float(data.get("expires_in") or 3600)
        updated = TokenData(
            access_token=new_access,
            refresh_token=str(data.get("refresh_token") or td.refresh_token),
            expires_at=time.time() + expires_in,
            token_type=str(data.get("token_type") or "Bearer"),
            scope=str(data.get("scope") or td.scope),
            extra=td.extra,
        )
        self.save(updated)
        logger.info("%s token refresh ok (expires_in=%.0fs)", self.platform, expires_in)
        return new_access

    def as_provider(self) -> Callable[[], str]:
        def _provider() -> str:
            return self.get_access_token()
        return _provider

    def set_tokens(
        self, access_token: str, refresh_token: str = "",
        expires_in: float = 3600, scope: str = "", **extra: Any,
    ) -> None:
        no_expiry = bool(extra.pop("no_expiry", False))
        expires_at = 0.0 if no_expiry else (time.time() + max(60.0, float(expires_in)))
        self.save(TokenData(
            access_token=access_token, refresh_token=refresh_token,
            expires_at=expires_at,
            scope=scope, extra=dict(extra) if extra else None,
            no_expiry=no_expiry,
        ))


def make_meta_token_store(
    platform: str = "instagram", *, tokens_path: str | Path | None = None,
    client_id: str = "", client_secret: str = "", http: ModuleHttpClient | None = None,
) -> OAuthTokenStore:
    path = tokens_path or os.getenv(
        f"{platform.upper()}_TOKENS_PATH", f"/opt/orchestrator/tokens/{platform}.json",
    )
    return OAuthTokenStore(
        platform, path, token_url=META_TOKEN_URL,
        client_id=client_id or os.getenv("META_APP_ID", ""),
        client_secret=client_secret or os.getenv("META_APP_SECRET", ""),
        http=http, refresh_grant_type="fb_exchange_token", refresh_token_param="fb_exchange_token",
    )


def make_tiktok_token_store(
    *, tokens_path: str | Path | None = None,
    client_id: str = "", client_secret: str = "", http: ModuleHttpClient | None = None,
) -> OAuthTokenStore:
    path = tokens_path or os.getenv("TIKTOK_TOKENS_PATH", "/opt/orchestrator/tokens/tiktok.json")
    return OAuthTokenStore(
        "tiktok", path, token_url=TIKTOK_TOKEN_URL,
        client_id=client_id or os.getenv("TIKTOK_CLIENT_KEY", ""),
        client_secret=client_secret or os.getenv("TIKTOK_CLIENT_SECRET", ""),
        http=http, refresh_grant_type="refresh_token",
    )
