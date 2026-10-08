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


class MeWeModule(PlatformModule):
    """MeWe Open API group-post adapter.

    The current public developer preview exposes server-side group posting,
    scheduled-post calendar/feed and group feed endpoints. This adapter keeps
    the supported surface explicit and does not claim arbitrary media upload,
    post edit or delete operations that are not part of the documented scope.
    """

    def __init__(self, *, token: str = "", app_id: str = "", group_id: str = "", base_url: str = "", http=None, **_: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.token = str(token or os.getenv("MEWE_API_TOKEN", "")).strip()
        self.app_id = str(app_id or os.getenv("MEWE_APP_ID", "")).strip()
        self.group_id = str(group_id or os.getenv("MEWE_GROUP_ID", "")).strip()
        self.base = str(base_url or os.getenv("MEWE_API_BASE", "https://mewe.com")).rstrip("/")
        self._http = http or ModuleHttpClient(platform="mewe", module_version=self.manifest.module_version)

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not self.app_id:
            errors.append("mewe: MEWE_APP_ID is required")
        if not self.token:
            errors.append("mewe: MEWE_API_TOKEN is required")
        if not self.group_id:
            errors.append("mewe: MEWE_GROUP_ID is required")
        return errors

    def _headers(self) -> dict[str, str]:
        if not self.app_id:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "MeWe: MEWE_APP_ID is required")
        if not self.token:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "MeWe: MEWE_API_TOKEN is required")
        return {
            "X-App-Id": self.app_id,
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    @staticmethod
    def _error(status: int, operation: str) -> ModuleError:
        if status in (401, 403):
            code = ModuleErrorCode.AUTH_EXPIRED
        elif status == 420 or status == 429:
            code = ModuleErrorCode.RATE_LIMIT
        elif status >= 500:
            code = ModuleErrorCode.TRANSIENT
        elif status in (400, 404):
            code = ModuleErrorCode.PLATFORM_REJECTED
        else:
            code = ModuleErrorCode.FATAL
        return ModuleError(
            code,
            f"MeWe {operation} HTTP {status}",
            retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT},
        )

    def auth_status(self) -> AuthStatus:
        try:
            r = self._http.request(
                "GET",
                f"{self.base}/api/dev/me",
                headers=self._headers(),
                idempotent=True,
            )
            if r.status_code >= 400:
                raise self._error(r.status_code, "me")
            data = r.json() if r.content else {}
            account = str(data.get("userId") or data.get("username") or self.group_id or "mewe")
            return AuthStatus(True, account=account, details="/api/dev/me ok")
        except ModuleError as exc:
            return AuthStatus(False, account=self.group_id or "mewe", details=exc.message)

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        kind = str(media.kind or "text").lower()
        if kind not in {"text", "image"}:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"MeWe: unsupported content kind {kind}")
        return PreparedMedia(path=media.path, kind=kind)

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if not self.group_id:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "MeWe: MEWE_GROUP_ID is required")
        text = str((meta.extra or {}).get("text") or meta.description or meta.title or "").strip()
        if not text:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "MeWe: post text is required")
        payload: dict[str, Any] = {"text": text}
        extra = dict(meta.extra or {})
        photo_ids = extra.get("uploadedPhotoIds") or extra.get("uploaded_photo_ids")
        if photo_ids:
            if not isinstance(photo_ids, list):
                photo_ids = [photo_ids]
            payload["uploadedPhotoIds"] = [str(x) for x in photo_ids]
        if extra.get("schedule") is not None:
            payload["schedule"] = int(extra["schedule"])
        elif extra.get("schedule_ms") is not None:
            payload["schedule"] = int(extra["schedule_ms"])

        r = self._http.request(
            "POST",
            f"{self.base}/api/dev/group/{self.group_id}/post",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=payload,
            idempotent=False,
        )
        if r.status_code >= 400:
            raise self._error(r.status_code, "group post")
        data = r.json() if r.content else {}
        external_id = str(data.get("postId") or data.get("id") or data.get("_id") or "")
        scheduled = payload.get("schedule") is not None
        return PublishResult(external_id=external_id, state="scheduled" if scheduled else "published")

    def get_status(self, external_id: str) -> PublishStatus:
        page = self.list_remote_items(limit=100)
        for item in page.items:
            if item.external_id == str(external_id):
                return PublishStatus(state="scheduled" if item.status == "scheduled" else "published", url=item.url, raw=item.raw)
        return PublishStatus(state="unknown")

    def schedule_publish(self, external_id: str, when) -> bool:
        raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED, "MeWe: scheduling is supplied on create via the schedule field")

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        endpoint = f"{self.base}/api/dev/group/{self.group_id}/postsfeed"
        params: dict[str, Any] = {"limit": min(max(1, int(limit)), 100)}
        if cursor:
            params["nextId"] = cursor
        r = self._http.request("GET", endpoint, headers=self._headers(), params=params, idempotent=True)
        if r.status_code >= 400:
            raise self._error(r.status_code, "group postsfeed")
        data = r.json() if r.content else {}
        rows = data.get("posts") or data.get("items") or []
        items: list[RemoteItem] = []
        for row in rows if isinstance(rows, list) else []:
            rid = str(row.get("id") or row.get("postId") or row.get("_id") or "")
            if not rid:
                continue
            published_at = row.get("createdAt") or row.get("publishedAt")
            status = str(row.get("status") or "published").lower()
            if "sched" in status:
                item_status = "scheduled"
            elif status in {"draft", "private"}:
                item_status = "private"
            else:
                item_status = "published"
            items.append(
                RemoteItem(
                    platform="mewe",
                    external_id=rid,
                    title=str(row.get("title") or ""),
                    description=str(row.get("text") or row.get("body") or row.get("description") or ""),
                    published_at=str(published_at) if published_at is not None else None,
                    status=item_status,
                    media_type="image" if row.get("uploadedPhotoIds") or row.get("photos") else "text",
                    raw=row,
                )
            )
        next_cursor = str(data.get("nextPage") or data.get("nextId") or "") or None
        return RemotePage(items=items, next_cursor=next_cursor)


def create_module(**deps: Any) -> MeWeModule:
    return MeWeModule(**deps)
