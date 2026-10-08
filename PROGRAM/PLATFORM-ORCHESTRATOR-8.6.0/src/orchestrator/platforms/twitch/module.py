from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...http_client import ModuleHttpClient
from ..base import AuthStatus, MediaSpec, ModuleError, ModuleErrorCode, PlatformModule, PreparedMedia, PublishMeta, PublishResult, PublishStatus, RemoteItem, RemotePage, NotSupported
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class TwitchModule(PlatformModule):
    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base = str(deps.get("base_url") or os.getenv("TWITCH_API_BASE", "https://api.twitch.tv/helix")).rstrip("/")
        self.client_id = str(deps.get("client_id") or os.getenv("TWITCH_CLIENT_ID", "")).strip()
        self.token = str(deps.get("access_token") or os.getenv("TWITCH_ACCESS_TOKEN", "")).strip()
        self.broadcaster_id = str(deps.get("broadcaster_id") or os.getenv("TWITCH_BROADCASTER_ID", "")).strip()
        self._http = deps.get("http") or ModuleHttpClient(platform="twitch", module_version=self.manifest.module_version)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Client-Id": self.client_id}

    @staticmethod
    def _error(status: int, action: str) -> ModuleError:
        code = ModuleErrorCode.AUTH_EXPIRED if status in (401, 403) else ModuleErrorCode.RATE_LIMIT if status == 429 else ModuleErrorCode.TRANSIENT if status >= 500 else ModuleErrorCode.PLATFORM_REJECTED
        return ModuleError(code, f"Twitch {action} HTTP {status}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        e: list[str] = []
        if not self.client_id:
            e.append("twitch: TWITCH_CLIENT_ID required")
        if not self.token:
            e.append("twitch: TWITCH_ACCESS_TOKEN required")
        if not self.broadcaster_id:
            e.append("twitch: TWITCH_BROADCASTER_ID required")
        return e

    def auth_status(self) -> AuthStatus:
        if not self.client_id or not self.token:
            return AuthStatus(False, account=self.broadcaster_id or "twitch", details="TWITCH_CLIENT_ID and TWITCH_ACCESS_TOKEN required")
        params = {"id": self.broadcaster_id} if self.broadcaster_id else None
        r = self._http.request("GET", f"{self.base}/users", headers=self._headers(), params=params)
        if r.status_code >= 400:
            return AuthStatus(False, account=self.broadcaster_id or "twitch", details=f"users HTTP {r.status_code}")
        rows = (r.json() if r.content else {}).get("data") or []
        if not rows:
            return AuthStatus(False, account=self.broadcaster_id or "twitch", details="broadcaster not found")
        d = rows[0]
        self.broadcaster_id = str(d.get("id") or self.broadcaster_id)
        return AuthStatus(True, account=str(d.get("login") or d.get("display_name") or self.broadcaster_id), details="users ok")

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        raise NotSupported("prepare/publish local media: Twitch Helix does not expose arbitrary file publishing")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        raise NotSupported("publish")

    def create_clip(self, *, title: str = "Clip", duration: int = 30) -> PublishResult:
        if not self.broadcaster_id:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Twitch: broadcaster_id required")
        if not 5 <= int(duration) <= 60:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Twitch: clip duration must be 5..60 seconds")
        r = self._http.request("POST", f"{self.base}/clips", headers=self._headers(), params={"broadcaster_id": self.broadcaster_id, "title": str(title)[:140], "duration": int(duration)}, idempotent=False)
        if r.status_code >= 400:
            raise self._error(r.status_code, "create clip")
        rows = (r.json() if r.content else {}).get("data") or []
        if not rows:
            raise ModuleError(ModuleErrorCode.FATAL, "Twitch: create clip returned no data")
        d = rows[0]
        cid = str(d.get("id") or "")
        if not cid:
            raise ModuleError(ModuleErrorCode.FATAL, "Twitch: create clip returned no id")
        return PublishResult(external_id=cid, url=str(d.get("edit_url") or f"https://clips.twitch.tv/{cid}"), state="processing")

    def create_clip_from_vod(self, *, vod_id: str, vod_offset: int, title: str = "Clip", duration: int = 30) -> PublishResult:
        if not self.broadcaster_id:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Twitch: broadcaster_id required")
        if not 5 <= int(duration) <= 60:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Twitch: clip duration must be 5..60 seconds")
        params = {"broadcaster_id": self.broadcaster_id, "vod_id": vod_id, "vod_offset": int(vod_offset), "title": str(title)[:140], "duration": int(duration)}
        r = self._http.request("POST", f"{self.base}/videos/clips", headers=self._headers(), params=params, idempotent=False)
        if r.status_code >= 400:
            raise self._error(r.status_code, "create VOD clip")
        rows = (r.json() if r.content else {}).get("data") or []
        if not rows:
            raise ModuleError(ModuleErrorCode.FATAL, "Twitch: create VOD clip returned no data")
        d = rows[0]
        cid = str(d.get("id") or "")
        if not cid:
            raise ModuleError(ModuleErrorCode.FATAL, "Twitch: create VOD clip returned no id")
        return PublishResult(external_id=cid, url=str(d.get("edit_url") or f"https://clips.twitch.tv/{cid}"), state="processing")

    def get_status(self, external_id: str) -> PublishStatus:
        r = self._http.request("GET", f"{self.base}/clips", headers=self._headers(), params={"id": external_id})
        if r.status_code == 404:
            return PublishStatus(state="unknown")
        if r.status_code >= 400:
            raise self._error(r.status_code, "get clip")
        rows = (r.json() if r.content else {}).get("data") or []
        if not rows:
            return PublishStatus(state="processing")
        d = rows[0]
        return PublishStatus(state="published", url=str(d.get("url") or f"https://clips.twitch.tv/{external_id}"), raw=d)

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        if not self.broadcaster_id:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Twitch: broadcaster_id required")
        first = min(max(1, int(limit)), 100)
        params: dict[str, Any] = {"broadcaster_id": self.broadcaster_id, "first": first}
        if cursor:
            params["after"] = cursor
        r = self._http.request("GET", f"{self.base}/clips", headers=self._headers(), params=params)
        if r.status_code >= 400:
            raise self._error(r.status_code, "list clips")
        body = r.json() if r.content else {}
        rows = body.get("data") or []
        pag = body.get("pagination") or {}
        items = [RemoteItem(platform="twitch", external_id=str(x.get("id") or ""), url=str(x.get("url") or ""), title=str(x.get("title") or ""), status="published", media_type="clip", duration_sec=float(x.get("duration") or 0), thumb_url=str(x.get("thumbnail_url") or ""), raw=x) for x in rows if x.get("id")]
        return RemotePage(items=items, next_cursor=str(pag.get("cursor")) if pag.get("cursor") else None)


def create_module(**deps: Any) -> TwitchModule:
    return TwitchModule(**deps)
