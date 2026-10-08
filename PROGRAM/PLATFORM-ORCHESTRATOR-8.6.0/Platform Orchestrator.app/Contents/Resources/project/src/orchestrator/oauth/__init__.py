"""OAuth manager for platform modules (platform-zero C2).

Authorization-code + PKCE flows; tokens land in local token stores,
never in platform Postgres.
"""
from __future__ import annotations

from .manager import OAuthManager, OAuthProviderConfig
from .sessions import OAuthSession, OAuthSessionStore

__all__ = [
    "OAuthManager",
    "OAuthProviderConfig",
    "OAuthSession",
    "OAuthSessionStore",
]
