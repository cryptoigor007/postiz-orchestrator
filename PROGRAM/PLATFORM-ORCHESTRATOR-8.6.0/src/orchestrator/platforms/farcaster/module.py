from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...http_client import ModuleHttpClient
from ..base import (
    AuthStatus,
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    NotSupported,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    PublishStatus,
    RemoteItem,
    RemotePage,
)
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class FarcasterModule(PlatformModule):
    """Farcaster partner adapter through Neynar's current v2 Cast API."""

    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base = str(deps.get("base_url") or os.getenv("NEYNAR_API_BASE", "https://api.neynar.com/v2")).rstrip("/")
        self.api_key = str(deps.get("api_key") or os.getenv("NEYNAR_API_KEY", "")).strip()
        self.signer_uuid = str(deps.get("signer_uuid") or os.getenv("FARCASTER_SIGNER_UUID", "")).strip()
        self.fid = str(deps.get("fid") or os.getenv("FARCASTER_FID", "")).strip()
        self._http = deps.get("http") or ModuleHttpClient(platform="farcaster", module_version=self.manifest.module_version)

    def _headers(self) -> dict[str, str]:
        return {"api_key": self.api_key, "Content-Type": "application/json"}

    @staticmethod
    def _error(status: int, action: str) -> ModuleError:
        if status in (401, 403):
            code = ModuleErrorCode.AUTH_EXPIRED
        elif status == 404:
            code = ModuleErrorCode.PLATFORM_REJECTED
        elif status == 429:
            code = ModuleErrorCode.RATE_LIMIT
        elif status >= 500:
            code = ModuleErrorCode.TRANSIENT
        else:
            code = ModuleErrorCode.PLATFORM_REJECTED
        return ModuleError(code, f"Farcaster/Neynar {action} HTTP {status}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def auth_status(self) -> AuthStatus:
        if not self.api_key:
            return AuthStatus(False, account=self.fid or "farcaster", details="NEYNAR_API_KEY missing")
        if self.fid:
            r = self._http.request("GET", f"{self.base}/farcaster/user/bulk", headers={"api_key": self.api_key}, params={"fids": self.fid})
            if r.status_code >= 400:
                return AuthStatus(False, account=self.fid, details=f"user/bulk HTTP {r.status_code}")
            users = (r.json() if r.content else {}).get("users") or []
            if not users:
                return AuthStatus(False, account=self.fid, details="FID not found")
            u = users[0]
            return AuthStatus(True, account=str(u.get("username") or u.get("display_name") or self.fid), details="user/bulk ok")
        return AuthStatus(True, account="farcaster", details="Neynar API key configured; FID not configured")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not self.api_key:
            errors.append("farcaster: NEYNAR_API_KEY required")
        if not self.signer_uuid:
            errors.append("farcaster: FARCASTER_SIGNER_UUID required for publishing/deleting")
        if not self.fid:
            errors.append("farcaster: FARCASTER_FID required for remote inventory")
        return errors

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        if media.kind not in ("text", ""):
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Farcaster: only text casts are supported by this adapter")
        return PreparedMedia(media.path, "text")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if not self.api_key or not self.signer_uuid:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Farcaster: NEYNAR_API_KEY and FARCASTER_SIGNER_UUID are required")
        extra = dict(meta.extra or {})
        text = str(extra.get("text") or meta.description or meta.title or "").strip()
        if not text:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Farcaster: cast text is empty")
        payload: dict[str, Any] = {"signer_uuid": self.signer_uuid, "text": text}
        embeds = extra.get("embeds")
        if embeds:
            payload["embeds"] = [{"url": str(x)} for x in embeds if str(x).strip()][:2]
        if extra.get("parent"):
            payload["parent"] = str(extra["parent"])
        if extra.get("parent_author_fid") is not None:
            payload["parent_author_fid"] = int(extra["parent_author_fid"])
        if extra.get("channel_id"):
            payload["channel_id"] = str(extra["channel_id"])
        r = self._http.request("POST", f"{self.base}/farcaster/cast", headers=self._headers(), json=payload, idempotent=False)
        if r.status_code >= 400:
            raise self._error(r.status_code, "publish cast")
        body = r.json() if r.content else {}
        cast = body.get("cast") or body.get("result", {}).get("cast") or body
        rid = str(cast.get("hash") or "") if isinstance(cast, dict) else ""
        if not rid:
            raise ModuleError(ModuleErrorCode.FATAL, "Farcaster: publish returned no cast hash")
        url = str(cast.get("url") or "") if isinstance(cast, dict) else ""
        return PublishResult(external_id=rid, url=url, state="published")

    def get_status(self, external_id: str) -> PublishStatus:
        r = self._http.request("GET", f"{self.base}/farcaster/cast", headers={"api_key": self.api_key}, params={"identifier": external_id, "type": "hash"})
        if r.status_code == 404:
            return PublishStatus(state="deleted")
        if r.status_code >= 400:
            raise self._error(r.status_code, "get cast")
        body = r.json() if r.content else {}
        cast = body.get("cast") or body.get("result", {}).get("cast") or body
        return PublishStatus(state="published", url=str(cast.get("url") or "") if isinstance(cast, dict) else "", raw=cast if isinstance(cast, dict) else {})

    def delete(self, external_id: str) -> bool:
        if not self.api_key or not self.signer_uuid:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Farcaster: API key and signer UUID required")
        r = self._http.request("DELETE", f"{self.base}/farcaster/cast/", headers={"api_key": self.api_key}, json={"signer_uuid": self.signer_uuid, "target_hash": external_id}, idempotent=True)
        if r.status_code == 404:
            return True
        if r.status_code >= 400:
            raise self._error(r.status_code, "delete cast")
        return True

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        raise NotSupported("update_metadata: Farcaster casts are immutable; create a new cast or delete the existing one")

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        if not self.api_key or not self.fid:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Farcaster: API key and FARCASTER_FID required for inventory")
        params: dict[str, Any] = {"fid": self.fid, "limit": min(max(1, int(limit)), 50)}
        if cursor:
            params["cursor"] = cursor
        r = self._http.request("GET", f"{self.base}/farcaster/feed/user/casts", headers={"api_key": self.api_key}, params=params)
        if r.status_code >= 400:
            raise self._error(r.status_code, "list user casts")
        body = r.json() if r.content else {}
        rows = body.get("casts") or []
        next_cursor = str((body.get("next") or {}).get("cursor") or "")
        items = [
            RemoteItem(
                platform="farcaster",
                external_id=str(x.get("hash") or ""),
                url=str(x.get("url") or ""),
                title=str(x.get("text") or "")[:120],
                description=str(x.get("text") or ""),
                published_at=str(x.get("timestamp") or "") or None,
                status="published",
                media_type="text",
                raw=x,
            )
            for x in rows if isinstance(x, dict) and x.get("hash")
        ]
        return RemotePage(items=items, next_cursor=next_cursor or None)


def create_module(**deps: Any) -> FarcasterModule:
    return FarcasterModule(**deps)
