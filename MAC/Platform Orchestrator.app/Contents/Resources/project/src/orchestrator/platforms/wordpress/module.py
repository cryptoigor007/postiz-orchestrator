from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from ..base import AuthStatus, MediaSpec, ModuleError, ModuleErrorCode, PlatformModule, PreparedMedia, PublishMeta, PublishResult, PublishStatus, RemoteItem, RemotePage
from ...http_client import ModuleHttpClient
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class WordPressModule(PlatformModule):
    """WordPress REST API v2 adapter for posts and reconciliation."""

    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base_url = str(deps.get("base_url") or os.getenv("WORDPRESS_BASE_URL", "")).rstrip("/")
        self.username = str(deps.get("username") or os.getenv("WORDPRESS_USERNAME", ""))
        self.app_password = str(deps.get("app_password") or os.getenv("WORDPRESS_APP_PASSWORD", ""))
        self._http = deps.get("http") or ModuleHttpClient(platform="wordpress", module_version=self.manifest.module_version)

    def _headers(self) -> dict[str, str]:
        raw = f"{self.username}:{self.app_password}".encode()
        return {"Authorization": "Basic " + base64.b64encode(raw).decode(), "Content-Type": "application/json"}

    @staticmethod
    def _error(status_code: int, operation: str) -> ModuleError:
        if status_code in (401, 403):
            code = ModuleErrorCode.AUTH_EXPIRED
        elif status_code == 429:
            code = ModuleErrorCode.RATE_LIMIT
        elif status_code >= 500:
            code = ModuleErrorCode.TRANSIENT
        else:
            code = ModuleErrorCode.PLATFORM_REJECTED
        return ModuleError(code, f"WordPress {operation} HTTP {status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def auth_status(self) -> AuthStatus:
        if not self.base_url or not self.username or not self.app_password:
            return AuthStatus(False, account=self.base_url or "wordpress", details="WORDPRESS_BASE_URL/USERNAME/APP_PASSWORD missing")
        response = self._http.request("GET", f"{self.base_url}/wp-json/wp/v2/users/me", headers=self._headers())
        if response.status_code >= 400:
            return AuthStatus(False, account=self.base_url, details=f"HTTP {response.status_code}")
        data = response.json() if response.content else {}
        return AuthStatus(True, account=str(data.get("name") or data.get("slug") or self.username), details="users/me ok")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not self.base_url:
            errors.append("wordpress: WORDPRESS_BASE_URL is required")
        if not self.username:
            errors.append("wordpress: WORDPRESS_USERNAME is required")
        if not self.app_password:
            errors.append("wordpress: WORDPRESS_APP_PASSWORD is required")
        return errors

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        kind = media.kind or "text"
        if kind != "text" and not Path(media.path).is_file():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"WordPress: file not found: {media.path}")
        return PreparedMedia(path=media.path, kind=kind)

    def _payload(self, media: PreparedMedia, meta: PublishMeta) -> dict[str, Any]:
        extra = dict(meta.extra or {})
        payload: dict[str, Any] = {
            "title": str(extra.get("title") or meta.title or Path(media.path).stem or "Untitled"),
            "content": str(extra.get("content") or meta.description or ""),
            "status": str(extra.get("status") or "publish"),
        }
        for key in ("excerpt", "slug", "author", "featured_media", "format", "sticky", "categories", "tags", "date", "date_gmt"):
            if key in extra:
                payload[key] = extra[key]
        return payload

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if not self.base_url:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "WordPress: base URL missing")
        payload = self._payload(media, meta)
        response = self._http.request("POST", f"{self.base_url}/wp-json/wp/v2/posts", headers=self._headers(), json=payload, idempotent=False)
        if response.status_code >= 400:
            raise self._error(response.status_code, "create post")
        data = response.json() if response.content else {}
        external_id = str(data.get("id") or "")
        if not external_id:
            raise ModuleError(ModuleErrorCode.FATAL, "WordPress: post create without id")
        return PublishResult(
            external_id=external_id,
            url=str(data.get("link") or ""),
            state="published" if payload["status"] == "publish" else "uploaded",
        )

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        extra = dict(patch.extra or {})
        payload: dict[str, Any] = {}
        if patch.title:
            payload["title"] = patch.title
        if patch.description or "content" in extra:
            payload["content"] = extra.get("content") if "content" in extra else patch.description
        for key in ("status", "excerpt", "slug", "author", "featured_media", "format", "sticky", "categories", "tags", "date", "date_gmt"):
            if key in extra:
                payload[key] = extra[key]
        if not payload:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WordPress: no metadata fields supplied")
        response = self._http.request("POST", f"{self.base_url}/wp-json/wp/v2/posts/{external_id}", headers=self._headers(), json=payload, idempotent=False)
        if response.status_code >= 400:
            raise self._error(response.status_code, "update post")
        return True

    def get_status(self, external_id: str) -> PublishStatus:
        response = self._http.request("GET", f"{self.base_url}/wp-json/wp/v2/posts/{external_id}", headers=self._headers())
        if response.status_code == 404:
            return PublishStatus(state="deleted")
        if response.status_code >= 400:
            raise self._error(response.status_code, "get post")
        data = response.json() if response.content else {}
        raw_status = str(data.get("status") or "unknown").lower()
        state = "published" if raw_status == "publish" else "uploaded"
        return PublishStatus(state=state, url=str(data.get("link") or ""), raw=data)

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        params: dict[str, Any] = {"page": int(cursor or 1), "per_page": min(max(1, int(limit)), 100), "context": "edit"}
        if since is not None:
            params["after"] = since.isoformat()
        if until is not None:
            params["before"] = until.isoformat()
        response = self._http.request("GET", f"{self.base_url}/wp-json/wp/v2/posts", headers=self._headers(), params=params)
        if response.status_code >= 400:
            raise self._error(response.status_code, "list posts")
        rows = response.json() if response.content else []
        if not isinstance(rows, list):
            rows = []
        items = [
            RemoteItem(
                platform="wordpress",
                external_id=str(row.get("id") or ""),
                url=str(row.get("link") or ""),
                title=str((row.get("title") or {}).get("rendered") or ""),
                description=str((row.get("content") or {}).get("rendered") or ""),
                published_at=str(row.get("date_gmt") or row.get("date") or "") or None,
                status="published" if str(row.get("status") or "") == "publish" else "private",
                media_type="text",
                raw=row,
            )
            for row in rows
            if isinstance(row, dict) and row.get("id")
        ]
        next_cursor = str(int(params["page"]) + 1) if len(rows) >= params["per_page"] else None
        return RemotePage(items=items, next_cursor=next_cursor)

    def delete(self, external_id: str) -> bool:
        response = self._http.request("DELETE", f"{self.base_url}/wp-json/wp/v2/posts/{external_id}", headers=self._headers(), params={"force": "true"}, idempotent=True)
        if response.status_code == 404:
            return True
        if response.status_code >= 400:
            raise self._error(response.status_code, "delete post")
        return True


def create_module(**deps: Any) -> WordPressModule:
    return WordPressModule(**deps)
