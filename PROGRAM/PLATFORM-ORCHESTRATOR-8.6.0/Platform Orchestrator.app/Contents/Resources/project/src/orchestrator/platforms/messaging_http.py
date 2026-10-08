"""Small reusable messaging helpers for native provider modules."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from ..http_client import ModuleHttpClient
import logging

logger = logging.getLogger(__name__)

from .base import AuthStatus, ModuleError, ModuleErrorCode
from .manifest import load_manifest

TokenProvider = Callable[[str, str], str]


def resolve_token(token_provider: TokenProvider | None, platform: str, account_id: str = "") -> str:
    if token_provider is not None:
        # Do not hide strict broker/auth failures: ProviderSupervisor must be able
        # to observe the real failure instead of silently downgrading to env tokens.
        tok = str(token_provider(platform, account_id) or "").strip()
        if tok:
            return tok
    keys = (f"{platform.upper()}_ACCESS_TOKEN",)
    if os.getenv("TOKEN_ALLOW_SHARED_ENV", "0").strip().lower() in {"1", "true", "yes", "on"}:
        keys = keys + ("ORCH_ACCESS_TOKEN",)
    for key in keys:
        tok = os.getenv(key, "").strip()
        if tok:
            return tok
    return ""


class NativeMessagingModule:
    """Base for messaging providers with common config/auth handling."""
    def __init__(self, *, platform: str, manifest_path: str | Path, token_provider: TokenProvider | None = None,
                 http: ModuleHttpClient | None = None, account_id: str = "", **_: Any) -> None:
        self.manifest = load_manifest(manifest_path)
        self._platform = platform
        self._token_provider = token_provider
        self._account_id = account_id or os.getenv(f"{platform.upper()}_ACCOUNT_ID", "")
        self._http = http or ModuleHttpClient(platform=platform, module_version=str(self.manifest.module_version))

    def auth_status(self) -> AuthStatus:
        tok = resolve_token(self._token_provider, self._platform, self._account_id)
        return AuthStatus(ok=bool(tok), account=self._account_id or self._platform,
                          details="token configured" if tok else "token missing")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        tok = resolve_token(self._token_provider, self._platform, self._account_id)
        return [] if tok else [f"{self._platform}: access token is required"]

    def _require_token(self) -> str:
        tok = resolve_token(self._token_provider, self._platform, self._account_id)
        if not tok:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, f"{self._platform}: access token is not configured")
        return tok

    def _json_or_error(self, response: Any) -> dict[str, Any]:
        if response.status_code >= 400:
            body = ""
            try:
                body = response.text[:1000]
            except Exception:
                logger.debug("provider error body unavailable", exc_info=True)
            code = ModuleErrorCode.RATE_LIMIT if response.status_code == 429 else (
                ModuleErrorCode.AUTH_EXPIRED if response.status_code in (401, 403) else ModuleErrorCode.FATAL
            )
            raise ModuleError(code, f"{self._platform}: HTTP {response.status_code}: {body}",
                              retryable=response.status_code in (429, 500, 502, 503, 504))
        try:
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}
        except Exception:
            return {"text": response.text}
