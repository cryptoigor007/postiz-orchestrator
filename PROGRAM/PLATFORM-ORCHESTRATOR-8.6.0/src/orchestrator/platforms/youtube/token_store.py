"""Локальное хранилище OAuth-токенов YouTube + auto-refresh.

См. docs/dev/03_API_STANDARDS.txt §1, MODULE_YOUTUBE.txt §3:
  tokens/youtube.json (600), access ~1ч, refresh за 10 мин до expiry
  или при AUTH_EXPIRED; invalid_grant → AUTH_REQUIRED.
Секреты (client_id/secret) — только из env; refresh_token не логируется.

Fail-closed (platform-zero C1):
  • expired + no refresh → AUTH_REQUIRED (не return stale access_token)
  • no client_id/secret при необходимости refresh → AUTH_REQUIRED
  • expires_at <= 0: не «вечно валиден»; policy TTL или require refresh
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from ...http_client import ModuleHttpClient, mask_secrets
from ..base import ModuleError, ModuleErrorCode

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
REFRESH_SKEW_SEC = 600  # 10 минут
NO_EXPIRY_POLICY_TTL_SEC = 3600


@dataclass
class TokenData:
    access_token: str
    refresh_token: str = ""
    expires_at: float = 0.0  # unix ts
    token_type: str = "Bearer"
    scope: str = ""
    no_expiry: bool = False

    def access_valid(self, skew: float = REFRESH_SKEW_SEC) -> bool:
        if not self.access_token:
            return False
        if self.expires_at <= 0:
            if self.no_expiry:
                return True
            return False
        return time.time() < (self.expires_at - skew)


class YouTubeTokenStore:
    """Файл tokens/youtube.json (права 600) + refresh через Google token endpoint."""

    def __init__(
        self,
        path: str | Path,
        *,
        client_id: str = "",
        client_secret: str = "",
        http: ModuleHttpClient | None = None,
        skew_sec: float = REFRESH_SKEW_SEC,
        no_expiry_policy_ttl: float = NO_EXPIRY_POLICY_TTL_SEC,
    ) -> None:
        self.path = Path(path)
        self.client_id = (client_id or os.getenv("YT_CLIENT_ID") or "").strip()
        self.client_secret = (client_secret or os.getenv("YT_CLIENT_SECRET") or "").strip()
        self.skew_sec = skew_sec
        self.no_expiry_policy_ttl = float(no_expiry_policy_ttl)
        self._http = http or ModuleHttpClient(
            platform="youtube",
            module_version="2.1.1",
            max_retries=3,
        )
        self._cache: TokenData | None = None
        self._lock_note = ""

    def load(self) -> TokenData | None:
        if not self.path.is_file():
            self._cache = None
            return None
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw) if raw.strip() else {}
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("youtube token_store: не удалось прочитать %s: %s", self.path, e)
            self._cache = None
            return None
        if not isinstance(data, dict):
            self._cache = None
            return None
        no_expiry = bool(data.get("no_expiry") or False)
        expires_at = float(data.get("expires_at") or 0)
        if expires_at <= 0 and data.get("expires_in"):
            try:
                expires_at = time.time() + float(data["expires_in"])
            except (TypeError, ValueError) as exc:
                logger.debug("youtube token_store invalid expires_in: %s", type(exc).__name__)
        if expires_at <= 0 and not no_expiry:
            updated_at = float(data.get("updated_at") or 0)
            if updated_at > 0 and self.no_expiry_policy_ttl > 0:
                expires_at = updated_at + self.no_expiry_policy_ttl
        td = TokenData(
            access_token=str(data.get("access_token") or data.get("token") or ""),
            refresh_token=str(data.get("refresh_token") or ""),
            expires_at=expires_at,
            token_type=str(data.get("token_type") or "Bearer"),
            scope=str(data.get("scope") or ""),
            no_expiry=no_expiry,
        )
        self._cache = td if td.access_token or td.refresh_token else None
        return self._cache

    def save(self, data: TokenData) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "access_token": data.access_token,
            "refresh_token": data.refresh_token,
            "expires_at": data.expires_at,
            "token_type": data.token_type or "Bearer",
            "scope": data.scope,
            "updated_at": time.time(),
        }
        if data.no_expiry:
            payload["no_expiry"] = True
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError as exc:
            logger.debug("youtube token_store chmod failed: %s", type(exc).__name__)
        self._cache = data
        logger.info(
            "youtube token_store: сохранён %s (expires_at=%.0f)",
            self.path.name,
            data.expires_at,
        )

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        """Вернуть access_token; при необходимости — refresh.

        Raises ModuleError(AUTH_REQUIRED) если refresh невозможен / invalid_grant.
        Fail-closed: never returns known-expired access without successful refresh.
        """
        td = self._cache if self._cache is not None else self.load()
        if td is None:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                "YouTube: нет токена (файл пуст или отсутствует).",
                action="подключите канал OAuth / положите tokens/youtube.json",
            )
        if not force_refresh and td.access_valid(self.skew_sec):
            return td.access_token

        if not td.refresh_token:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                "YouTube: access token expired and no refresh_token — "
                "переподключите канал (OAuth offline).",
                action="переподключить YouTube в панели; выдать новый refresh",
            )
        return self._do_refresh(td)

    def _do_refresh(self, td: TokenData) -> str:
        if not self.client_id or not self.client_secret:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                "YouTube: нет YT_CLIENT_ID/YT_CLIENT_SECRET для refresh.",
                action="задайте client_id/secret в .env (600)",
            )
        body = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": td.refresh_token,
            "grant_type": "refresh_token",
        }
        try:
            resp = self._http.request(
                "POST",
                TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=urlencode(body).encode("utf-8"),
                idempotent=True,
            )
        except Exception as e:
            logger.warning("youtube token refresh network: %s", type(e).__name__)
            raise ModuleError(
                ModuleErrorCode.TRANSIENT,
                f"YouTube: сеть при refresh токена: {type(e).__name__}",
                action="повтор с backoff",
                retryable=True,
            ) from e

        if resp.status_code >= 400:
            try:
                err_body = resp.json()
            except Exception:
                err_body = {"error": (resp.text or "")[:300]}
            err = str((err_body or {}).get("error") or "")
            desc = str((err_body or {}).get("error_description") or "")
            low = (err + " " + desc).lower()
            if "invalid_grant" in low or resp.status_code in (400, 401):
                logger.warning(
                    "youtube token refresh invalid_grant (masked): %s",
                    mask_secrets(desc or err),
                )
                raise ModuleError(
                    ModuleErrorCode.AUTH_REQUIRED,
                    "YouTube: refresh-токен недействителен (invalid_grant). "
                    "Переподключите канал (OAuth).",
                    action="переподключить YouTube в панели / новый refresh",
                    retryable=False,
                )
            raise ModuleError(
                ModuleErrorCode.TRANSIENT if resp.status_code >= 500 else ModuleErrorCode.FATAL,
                f"YouTube: ошибка refresh ({resp.status_code}): {mask_secrets(desc or err)}",
                action="повтор или переподключение",
                retryable=resp.status_code >= 500,
            )

        try:
            data = resp.json() if resp.content else {}
        except Exception as e:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                "YouTube: невалидный JSON при refresh",
                action="проверьте ответ Google token endpoint",
            ) from e

        new_access = str(data.get("access_token") or "")
        if not new_access:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                "YouTube: refresh без access_token",
                action="проверьте client_id/secret и scopes",
            )
        expires_in = float(data.get("expires_in") or 3600)
        new_refresh = str(data.get("refresh_token") or td.refresh_token)
        updated = TokenData(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_at=time.time() + expires_in,
            token_type=str(data.get("token_type") or "Bearer"),
            scope=str(data.get("scope") or td.scope),
            no_expiry=False,
        )
        self.save(updated)
        logger.info("youtube token refresh ok (expires_in=%.0fs)", expires_in)
        return new_access

    def as_provider(self) -> Callable[[], str]:
        def _provider() -> str:
            return self.get_access_token()
        return _provider

    def set_tokens(
        self,
        access_token: str,
        refresh_token: str = "",
        expires_in: float = 3600,
        scope: str = "",
        *,
        no_expiry: bool = False,
    ) -> None:
        td = TokenData(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=0.0 if no_expiry else (time.time() + max(60.0, float(expires_in))),
            scope=scope,
            no_expiry=no_expiry,
        )
        self.save(td)


def make_token_provider(
    *,
    token_provider: Callable[[], str] | None = None,
    tokens_path: str | Path | None = None,
    client_id: str = "",
    client_secret: str = "",
    http: ModuleHttpClient | None = None,
) -> Callable[[], str]:
    if callable(token_provider):
        return token_provider
    path = tokens_path or os.getenv("YT_TOKENS_PATH") or "/opt/orchestrator/tokens/youtube.json"
    store = YouTubeTokenStore(
        path,
        client_id=client_id,
        client_secret=client_secret,
        http=http,
    )
    if store.load() is not None or (store.client_id and store.client_secret):
        return store.as_provider()

    def _empty() -> str:
        return ""

    return _empty
