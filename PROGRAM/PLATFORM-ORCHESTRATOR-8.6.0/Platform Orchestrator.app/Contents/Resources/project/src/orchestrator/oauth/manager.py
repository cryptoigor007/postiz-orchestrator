"""OAuth authorization-code + PKCE manager (platform-zero C2).

Supports Google (YouTube), Meta, TikTok provider configs.
Tokens are written to local token stores — never platform DB.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlencode

from ..http_client import ModuleHttpClient, mask_secrets
from ..platforms.base import ModuleError, ModuleErrorCode
from .sessions import (
    OAuthSession,
    OAuthSessionStore,
    new_pkce_pair,
    new_state,
)

logger = logging.getLogger(__name__)

def meta_graph_version(cfg: Any = None) -> str:
    """Graph API version from config.oauth.meta_graph_version or env, default v26.0."""
    import os
    if cfg is not None:
        oauth = getattr(cfg, "oauth", None) or {}
        if isinstance(oauth, dict) and oauth.get("meta_graph_version"):
            return str(oauth["meta_graph_version"]).strip()
        # AppConfig may not have oauth attr — try engines/raw
    return (os.getenv("META_GRAPH_VERSION") or "v26.0").strip()


def make_meta_provider(
    client_id: str = "",
    client_secret: str = "",
    graph_version: str | None = None,
    *,
    provider: str = "meta",
    strategy: str = "meta",
    scopes: list[str] | None = None,
) -> OAuthProviderConfig:
    """Build a Meta-family OAuth provider with explicit product/scopes.

    One generic Meta OAuth config is deliberately avoided: Facebook Pages,
    Instagram, Threads and future Meta products have different permissions.
    """
    ver = graph_version or meta_graph_version()
    if not ver.startswith("v"):
        ver = f"v{ver}"
    default_scopes = {
        "facebook": ["pages_show_list", "pages_read_engagement", "pages_manage_posts"],
        "instagram": ["instagram_basic", "instagram_content_publish", "pages_show_list", "pages_read_engagement"],
        "threads": ["threads_basic", "threads_content_publish"],
        "meta": [],
    }
    chosen = list(scopes if scopes is not None else default_scopes.get(provider, []))
    return OAuthProviderConfig(
        provider=provider,
        client_id=client_id,
        client_secret=client_secret,
        authorize_url=f"https://www.facebook.com/{ver}/dialog/oauth",
        token_url=f"https://graph.facebook.com/{ver}/oauth/access_token",
        scopes=chosen,
        extra_auth_params={"meta_strategy": strategy},
        use_pkce=False,
    )


@dataclass
class OAuthProviderConfig:
    """Per-provider OAuth settings (from config / env)."""
    provider: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scopes: list[str] = field(default_factory=list)
    extra_auth_params: dict[str, str] = field(default_factory=dict)
    # PKCE required by default for public clients; Meta may omit for confidential
    use_pkce: bool = True


# Built-in defaults (URLs only; secrets from env/config)
GOOGLE_YOUTUBE = OAuthProviderConfig(
    provider="youtube",
    client_id="",
    client_secret="",
    authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url="https://oauth2.googleapis.com/token",
    scopes=[
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    ],
    extra_auth_params={"access_type": "offline", "prompt": "consent"},
    use_pkce=True,
)

META = make_meta_provider()
FACEBOOK = make_meta_provider(provider="facebook", strategy="meta_page")
INSTAGRAM = make_meta_provider(provider="instagram", strategy="meta_ig")
THREADS = make_meta_provider(provider="threads", strategy="threads")

TIKTOK = OAuthProviderConfig(
    provider="tiktok",
    client_id="",
    client_secret="",
    authorize_url="https://www.tiktok.com/v2/auth/authorize/",
    token_url="https://open.tiktokapis.com/v2/oauth/token/",
    scopes=["video.upload", "video.publish"],
    use_pkce=True,
)


@dataclass
class OAuthStartResult:
    authorize_url: str
    state: str
    session_id: str


@dataclass
class OAuthTokenResult:
    access_token: str
    refresh_token: str = ""
    expires_in: float = 3600.0
    token_type: str = "Bearer"
    scope: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class OAuthManager:
    """Start OAuth (PKCE) and handle callback → tokens."""

    def __init__(
        self,
        *,
        public_base_url: str,
        session_store: OAuthSessionStore,
        providers: dict[str, OAuthProviderConfig] | None = None,
        http: ModuleHttpClient | None = None,
        token_saver: Callable[[str, OAuthTokenResult, str], None] | None = None,
        account_store: Any = None,
    ) -> None:
        self.public_base_url = public_base_url.rstrip("/")
        self.sessions = session_store
        self.providers = dict(providers or {})
        self._http = http or ModuleHttpClient(
            platform="oauth", module_version="0.1.0", max_retries=2,
        )
        # token_saver(provider, result, account_hint) → write to token store
        self._token_saver = token_saver
        self._account_store = account_store

    def callback_uri(self, provider: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/webapp/api/oauth/callback/{provider}"

    def start(
        self,
        provider: str,
        *,
        account_hint: str = "",
        extra_scopes: list[str] | None = None,
    ) -> OAuthStartResult:
        cfg = self._cfg(provider)
        if not cfg.client_id:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth {provider}: client_id not configured",
                action="задайте client_id/secret в config/env",
            )
        state = new_state()
        verifier, challenge = ("", "")
        if cfg.use_pkce:
            verifier, challenge = new_pkce_pair()
        redirect_uri = self.callback_uri(provider)
        sess = self.sessions.create(
            provider=provider,
            code_verifier=verifier or "nopkce",
            state=state,
            redirect_uri=redirect_uri,
            account_hint=account_hint,
        )
        scopes = list(cfg.scopes)
        if extra_scopes:
            scopes.extend(extra_scopes)
        params: dict[str, str] = {
            "client_id": cfg.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        if scopes:
            params["scope"] = " ".join(scopes)
        if cfg.use_pkce and challenge:
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "S256"
        params.update(cfg.extra_auth_params)
        url = cfg.authorize_url + "?" + urlencode(params)
        return OAuthStartResult(
            authorize_url=url, state=state, session_id=sess.id,
        )

    def handle_callback(
        self,
        provider: str,
        *,
        code: str,
        state: str,
    ) -> OAuthTokenResult:
        if not code or not state:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth {provider}: missing code/state",
                action="повторите OAuth start",
            )
        sess = self.sessions.get_by_state(state)
        if sess is None:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth {provider}: unknown state",
                action="повторите OAuth start",
            )
        if sess.provider != provider.strip().lower():
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth {provider}: provider mismatch",
                action="повторите OAuth start",
            )
        if sess.consumed:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth {provider}: state already consumed",
                action="повторите OAuth start",
            )
        if sess.processing:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth {provider}: state callback already in progress",
                action="дождитесь завершения первого callback",
                retryable=True,
            )
        if sess.expired:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth {provider}: state expired",
                action="повторите OAuth start",
            )
        if not self.sessions.claim(sess.id):
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth {provider}: state was already claimed",
                action="повторите OAuth start",
                retryable=True,
            )
        cfg = self._cfg(provider)
        body: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": sess.redirect_uri,
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
        }
        if cfg.use_pkce and sess.code_verifier and sess.code_verifier != "nopkce":
            body["code_verifier"] = sess.code_verifier
        try:
            resp = self._http.request(
                "POST",
                cfg.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                content=urlencode(body).encode("utf-8"),
                idempotent=False,
            )
        except Exception as e:
            self.sessions.release_claim(sess.id)
            raise ModuleError(
                ModuleErrorCode.TRANSIENT,
                f"OAuth {provider}: token exchange network: {type(e).__name__}",
                action="повторить",
                retryable=True,
            ) from e
        if resp.status_code >= 400:
            self.sessions.release_claim(sess.id)
            text = mask_secrets((resp.text or "")[:400])
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth {provider}: token exchange HTTP {resp.status_code}: {text}",
                action="проверьте client_id/secret и redirect_uri",
            )
        try:
            data = resp.json() if resp.content else {}
        except Exception as e:
            self.sessions.release_claim(sess.id)
            raise ModuleError(
                ModuleErrorCode.FATAL,
                f"OAuth {provider}: invalid token JSON",
                action="проверьте token endpoint",
            ) from e
        access = str(data.get("access_token") or "")
        if not access:
            self.sessions.release_claim(sess.id)
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth {provider}: no access_token in response",
                action="повторите OAuth",
            )
        result = OAuthTokenResult(
            access_token=access,
            refresh_token=str(data.get("refresh_token") or ""),
            expires_in=float(data.get("expires_in") or 3600),
            token_type=str(data.get("token_type") or "Bearer"),
            scope=str(data.get("scope") or ""),
            raw=dict(data) if isinstance(data, dict) else {},
        )
        # Persist first. A failed token write must not consume the OAuth state or enable an account.
        if self._token_saver:
            try:
                self._token_saver(provider, result, sess.account_hint)
            except Exception as e:
                logger.warning("oauth token_saver failed: %s", type(e).__name__)
                self.sessions.release_claim(sess.id)
                raise ModuleError(
                    ModuleErrorCode.FATAL,
                    f"OAuth {provider}: token save failed: {e}",
                    action="проверьте tokens/ path permissions",
                ) from e
        self.sessions.mark_consumed(sess.id)
        if self._account_store is not None:
            try:
                hint = (sess.account_hint or "").strip()
                token_root = os.getenv("TOKENS_DIR", "tokens").rstrip("/") or "tokens"
                self._account_store.upsert(
                    platform=provider.strip().lower(),
                    external_account_id=hint,
                    name=hint or provider,
                    auth_provider=provider.strip().lower(),
                    token_ref=f"{token_root}/{provider.strip().lower()}__{hint}.json" if hint else f"{token_root}/{provider.strip().lower()}.json",
                    enabled=True,
                    account_id=hint or None,
                    connection_state="CONNECTED",
                    expires_at=time.time() + result.expires_in,
                    granted_scopes=result.scope,
                    refresh_status="available" if result.refresh_token else "none",
                )
            except Exception:
                logger.warning("oauth platform_accounts bind failed", exc_info=True)
        logger.info("oauth %s: tokens obtained (expires_in=%.0f)", provider, result.expires_in)
        return result

    def _cfg(self, provider: str) -> OAuthProviderConfig:
        key = provider.strip().lower()
        if key not in self.providers:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"OAuth provider not configured: {provider}",
                action="добавьте provider в OAuthManager.providers",
            )
        return self.providers[key]
