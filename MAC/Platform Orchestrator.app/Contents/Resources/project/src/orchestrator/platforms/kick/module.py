from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..base import AuthStatus, ModuleError, ModuleErrorCode, NotSupported, PlatformModule, PreparedMedia, MediaSpec, PublishMeta, PublishStatus, RemoteItem, RemotePage
from ..manifest import load_manifest
from ...http_client import ModuleHttpClient

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class KickModule(PlatformModule):
    """Native KICK Public API surface where the 2026 public contract is confirmed.

    KICK currently exposes channel/livestream APIs and channel metadata updates; this
    adapter deliberately does not claim arbitrary server-side video upload because the
    public docs do not expose such a publishing endpoint.
    """

    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base = str(deps.get("base_url") or os.getenv("KICK_API_BASE", "https://api.kick.com")).rstrip("/")
        self.token = str(deps.get("token") or os.getenv("KICK_ACCESS_TOKEN", "")).strip()
        self.channel_id = str(deps.get("channel_id") or os.getenv("KICK_BROADCASTER_USER_ID", "")).strip()
        self.slug = str(deps.get("slug") or os.getenv("KICK_CHANNEL_SLUG", "")).strip()
        self._http = deps.get("http") or ModuleHttpClient(platform="kick", module_version=self.manifest.module_version)

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not self.token:
            errors.append("kick: KICK_ACCESS_TOKEN is required")
        if not self.channel_id and not self.slug:
            errors.append("kick: KICK_BROADCASTER_USER_ID or KICK_CHANNEL_SLUG is required")
        return errors

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Kick: KICK_ACCESS_TOKEN is required")
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    @staticmethod
    def _error(status: int, operation: str) -> ModuleError:
        if status in (401, 403):
            code = ModuleErrorCode.AUTH_EXPIRED
        elif status == 429:
            code = ModuleErrorCode.RATE_LIMIT
        elif status >= 500:
            code = ModuleErrorCode.TRANSIENT
        else:
            code = ModuleErrorCode.PLATFORM_REJECTED
        return ModuleError(code, f"Kick {operation} HTTP {status}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def auth_status(self) -> AuthStatus:
        try:
            response = self._http.request("GET", f"{self.base}/public/v1/channels", headers=self._headers(), params=self._channel_params())
            if response.status_code >= 400:
                raise self._error(response.status_code, "channels")
            data = response.json() if response.content else {}
            rows = data.get("data") or data.get("channels") or []
            return AuthStatus(True, account=self.channel_id or self.slug or "kick", details=f"channels={len(rows) if isinstance(rows, list) else 1}")
        except ModuleError as exc:
            return AuthStatus(False, account=self.channel_id or self.slug or "kick", details=exc.message)

    def _channel_params(self) -> dict[str, Any]:
        if self.channel_id:
            return {"broadcaster_user_id": self.channel_id}
        return {"slug": self.slug}

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        raise NotSupported("prepare/publish: KICK public API does not expose arbitrary server-side video upload")

    def publish(self, media: PreparedMedia, meta: PublishMeta):
        raise NotSupported("publish")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        if not self.channel_id:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Kick: KICK_BROADCASTER_USER_ID is required for channel update")
        body: dict[str, Any] = {}
        extra = dict(patch.extra or {})
        for key in ("title", "category_id", "language", "custom_tags"):
            if key in extra:
                body[key] = extra[key]
        if patch.title:
            body["stream_title"] = patch.title
        if not body:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Kick: update patch is empty")
        response = self._http.request("PATCH", f"{self.base}/public/v1/channels", headers={**self._headers(), "Content-Type": "application/json"}, params=self._channel_params(), json=body, idempotent=False)
        if response.status_code >= 400:
            raise self._error(response.status_code, "channel patch")
        return True

    def get_status(self, external_id: str) -> PublishStatus:
        response = self._http.request("GET", f"{self.base}/public/v1/livestreams", headers=self._headers(), params={"broadcaster_user_id": external_id or self.channel_id})
        if response.status_code >= 400:
            if response.status_code == 404:
                return PublishStatus(state="deleted")
            raise self._error(response.status_code, "livestreams")
        data = response.json() if response.content else {}
        rows = data.get("data") or data.get("livestreams") or []
        row = rows[0] if isinstance(rows, list) and rows else None
        if not row:
            return PublishStatus(state="unknown", raw=data)
        return PublishStatus(state="published" if row.get("is_live") or row.get("status") in ("live", "started") else "unknown", raw=row)

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        params: dict[str, Any] = {"limit": min(max(1, int(limit)), 100)}
        if self.channel_id:
            params["broadcaster_user_id"] = self.channel_id
        response = self._http.request("GET", f"{self.base}/public/v1/livestreams", headers=self._headers(), params=params)
        if response.status_code >= 400:
            raise self._error(response.status_code, "list livestreams")
        data = response.json() if response.content else {}
        rows = data.get("data") or data.get("livestreams") or []
        items: list[RemoteItem] = []
        for row in rows if isinstance(rows, list) else []:
            items.append(
                RemoteItem(
                    platform="kick",
                    external_id=str(row.get("id") or row.get("livestream_id") or ""),
                    title=str(row.get("session_title") or row.get("title") or ""),
                    description=str(row.get("description") or ""),
                    published_at=str(row.get("start_time") or row.get("created_at") or "") or None,
                    status="published" if row.get("is_live") or row.get("status") == "live" else "processing",
                    media_type="video",
                    thumb_url=str(row.get("thumbnail_url") or ""),
                    raw=row,
                )
            )
        return RemotePage(items=items)


def create_module(**deps: Any) -> KickModule:
    return KickModule(**deps)
