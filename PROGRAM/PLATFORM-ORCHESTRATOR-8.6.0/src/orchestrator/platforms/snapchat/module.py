from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..base import (
    AuthStatus,
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    PublishStatus,
    RemoteItem,
    RemotePage,
)
from ..manifest import load_manifest
from ...http_client import ModuleHttpClient

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class SnapchatModule(PlatformModule):
    """Snapchat Public Profile API adapter.

    The documented organic publishing flow is two-stage: upload encrypted media
    into a media object and then post that media to a Story or Spotlight. This
    adapter consumes an already-created provider media_id so it never pretends
    that a local file has been uploaded when no live encrypted upload context is
    available. Story/Spotlight inventory is also supported.
    """

    def __init__(self, *, token: str = "", profile_id: str = "", base_url: str = "", http=None, **_: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.token = str(token or os.getenv("SNAPCHAT_ACCESS_TOKEN", "")).strip()
        self.profile_id = str(profile_id or os.getenv("SNAPCHAT_PROFILE_ID", "")).strip()
        self.base = str(base_url or os.getenv("SNAPCHAT_API_BASE", "https://businessapi.snapchat.com/v1")).rstrip("/")
        self._http = http or ModuleHttpClient(platform="snapchat", module_version=self.manifest.module_version)

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not self.token:
            errors.append("snapchat: SNAPCHAT_ACCESS_TOKEN is required")
        if not self.profile_id:
            errors.append("snapchat: SNAPCHAT_PROFILE_ID is required")
        return errors

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Snapchat: SNAPCHAT_ACCESS_TOKEN is required")
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    @staticmethod
    def _error(status: int, operation: str) -> ModuleError:
        if status in (401, 403):
            code = ModuleErrorCode.AUTH_EXPIRED
        elif status == 429:
            code = ModuleErrorCode.RATE_LIMIT
        elif status >= 500:
            code = ModuleErrorCode.TRANSIENT
        elif status in (400, 404):
            code = ModuleErrorCode.PLATFORM_REJECTED
        else:
            code = ModuleErrorCode.FATAL
        return ModuleError(code, f"Snapchat {operation} HTTP {status}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def auth_status(self) -> AuthStatus:
        try:
            r = self._http.request("GET", f"{self.base}/public_profiles/{self.profile_id}", headers=self._headers(), idempotent=True)
            if r.status_code >= 400:
                raise self._error(r.status_code, "profile")
            data = r.json() if r.content else {}
            return AuthStatus(True, account=self.profile_id, details="Public Profile API access ok")
        except ModuleError as exc:
            return AuthStatus(False, account=self.profile_id or "snapchat", details=exc.message)

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        kind = str(media.kind or "video").lower()
        if kind not in {"image", "video"}:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"Snapchat: unsupported content kind {kind}")
        return PreparedMedia(path=media.path, kind=kind)

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        extra = dict(meta.extra or {})
        media_id = str(extra.get("media_id") or extra.get("snap_media_id") or "").strip()
        if not media_id:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Snapchat: provider media_id is required; upload media through the documented encrypted media flow first")
        mode = str(extra.get("destination") or "story").strip().lower()
        if mode == "story":
            payload: dict[str, Any] = {"media_id": media_id}
            ttl = extra.get("ttl") or extra.get("customized_ttl")
            if ttl:
                value = {"ttl": str(ttl).upper()} if isinstance(ttl, str) else ttl
                payload["customized_ttl"] = value
            path = f"{self.base}/public_profiles/{self.profile_id}/stories"
        elif mode == "spotlight":
            payload = {
                "media_id": media_id,
                "skip_save_to_profile": bool(extra.get("skip_save_to_profile", False)),
                "description": str(extra.get("description") or meta.description or meta.title or ""),
                "locale": str(extra.get("locale") or "en_US"),
            }
            path = f"{self.base}/public_profiles/{self.profile_id}/spotlights"
        else:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"Snapchat: unsupported destination {mode}")

        r = self._http.request("POST", path, headers={**self._headers(), "Content-Type": "application/json"}, json=payload, idempotent=False)
        if r.status_code >= 400:
            raise self._error(r.status_code, f"{mode} publish")
        data = r.json() if r.content else {}
        if str(data.get("request_status") or "SUCCESS").upper() not in {"SUCCESS", "PARTIAL"}:
            raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED, str(data.get("display_message") or data.get("debug_message") or "Snapchat publish rejected"))
        external_id = str(data.get("story_id") or data.get("spotlight_id") or data.get("id") or data.get("request_id") or media_id)
        return PublishResult(external_id=external_id, state="published")

    def get_status(self, external_id: str) -> PublishStatus:
        page = self.list_remote_items(limit=100)
        for item in page.items:
            if item.external_id == str(external_id):
                return PublishStatus(state="published", url=item.url, raw=item.raw)
        return PublishStatus(state="unknown")

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        mode = "story"
        if kinds and any("spotlight" in str(k).lower() for k in kinds):
            mode = "spotlight"
        path = f"{self.base}/public_profiles/{self.profile_id}/{('stories' if mode == 'story' else 'spotlights')}"
        params: dict[str, Any] = {"limit": min(max(1, int(limit)), 100)}
        if cursor:
            params["cursor"] = cursor
        r = self._http.request("GET", path, headers=self._headers(), params=params, idempotent=True)
        if r.status_code >= 400:
            raise self._error(r.status_code, f"{mode} inventory")
        data = r.json() if r.content else {}
        rows = data.get("stories") if mode == "story" else data.get("spotlights")
        rows = rows or []
        items: list[RemoteItem] = []
        for entry in rows if isinstance(rows, list) else []:
            row = entry.get("story") if isinstance(entry, dict) and entry.get("story") else entry.get("spotlight") if isinstance(entry, dict) and entry.get("spotlight") else entry
            if not isinstance(row, dict):
                continue
            rid = str(row.get("id") or row.get("story_id") or row.get("spotlight_id") or "")
            if not rid:
                continue
            items.append(
                RemoteItem(
                    platform="snapchat",
                    external_id=rid,
                    title=str(row.get("description") or ""),
                    description=str(row.get("caption") or row.get("description") or ""),
                    published_at=str(row.get("created_at") or "") or None,
                    status="published",
                    media_type="story" if mode == "story" else "video",
                    thumb_url=str(row.get("thumbnail_url") or ""),
                    raw=row,
                )
            )
        paging = data.get("paging") or {}
        next_cursor = str(paging.get("next_page_id") or "") or None
        return RemotePage(items=items, next_cursor=next_cursor)


def create_module(**deps: Any) -> SnapchatModule:
    return SnapchatModule(**deps)
