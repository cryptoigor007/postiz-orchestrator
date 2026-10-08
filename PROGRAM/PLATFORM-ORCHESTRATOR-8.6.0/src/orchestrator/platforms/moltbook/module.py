from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

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


class MoltbookModule(PlatformModule):
    """Moltbook REST adapter for agent text posts.

    The provider currently exposes create/read/delete endpoints for posts.  Delete is
    verified by a follow-up GET because the live API has had confirmed cases where
    DELETE returned success while the post remained visible.
    """

    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base = str(deps.get("base_url") or os.getenv("MOLTBOOK_API_BASE", "https://www.moltbook.com/api/v1")).rstrip("/")
        self.api_key = str(deps.get("api_key") or os.getenv("MOLTBOOK_API_KEY", "")).strip()
        self.submolt = str(deps.get("submolt") or os.getenv("MOLTBOOK_SUBMOLT", "general")).strip()
        self._http = deps.get("http") or ModuleHttpClient(platform="moltbook", module_version=self.manifest.module_version)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Moltbook: MOLTBOOK_API_KEY is required")
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

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
        return ModuleError(code, f"Moltbook {operation} HTTP {status}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        return [] if self.api_key else ["MOLTBOOK_API_KEY is required"]

    def auth_status(self) -> AuthStatus:
        if not self.api_key:
            return AuthStatus(False, account="moltbook", details="MOLTBOOK_API_KEY is required")
        try:
            response = self._http.request("GET", f"{self.base}/agents/me", headers=self._headers())
            if response.status_code >= 400:
                raise self._error(response.status_code, "agents/me")
            data = response.json() if response.content else {}
            agent = data.get("agent") or data.get("data") or data
            name = str(agent.get("name") or agent.get("username") or "moltbook") if isinstance(agent, dict) else "moltbook"
            return AuthStatus(True, account=name, details="agents/me ok")
        except ModuleError as exc:
            return AuthStatus(False, account="moltbook", details=exc.message)

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        if (media.kind or "text") != "text":
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Moltbook: only text/link posts are supported")
        return PreparedMedia(path=media.path, kind="text")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        title = str(meta.title or "").strip()
        extra = dict(meta.extra or {})
        content = str(extra.get("content") or meta.description or "").strip()
        submolt = str(extra.get("submolt") or self.submolt).strip()
        url = str(extra.get("url") or "").strip()
        if not title:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Moltbook: title is required")
        if not content and not url:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Moltbook: content or url is required")
        payload: dict[str, Any] = {"submolt": submolt, "title": title}
        if content:
            payload["content"] = content
        if url:
            payload["url"] = url
        response = self._http.request("POST", f"{self.base}/posts", headers={**self._headers(), "Content-Type": "application/json"}, json=payload, idempotent=False)
        if response.status_code >= 400:
            raise self._error(response.status_code, "create post")
        data = response.json() if response.content else {}
        post = data.get("post") or data.get("data") or data
        external_id = str(post.get("id") or post.get("post_id") or "") if isinstance(post, dict) else ""
        if not external_id:
            raise ModuleError(ModuleErrorCode.FATAL, "Moltbook: create post returned no id")
        return PublishResult(external_id=external_id, url=str(post.get("url") or "") if isinstance(post, dict) else "", state="published")

    def get_status(self, external_id: str) -> PublishStatus:
        response = self._http.request("GET", f"{self.base}/posts/{external_id}", headers=self._headers())
        if response.status_code == 404:
            return PublishStatus(state="deleted")
        if response.status_code >= 400:
            raise self._error(response.status_code, "get post")
        data = response.json() if response.content else {}
        post = data.get("post") or data.get("data") or data
        if not isinstance(post, dict):
            return PublishStatus(state="unknown", raw={"response": data})
        return PublishStatus(state="published", url=str(post.get("url") or ""), raw=post)

    def delete(self, external_id: str) -> bool:
        response = self._http.request("DELETE", f"{self.base}/posts/{external_id}", headers=self._headers(), idempotent=False)
        if response.status_code >= 400:
            raise self._error(response.status_code, "delete post")
        # The live API has an observed false-success delete behavior, so verify it.
        verify = self._http.request("GET", f"{self.base}/posts/{external_id}", headers=self._headers())
        if verify.status_code == 404:
            return True
        if verify.status_code < 400:
            raise ModuleError(
                ModuleErrorCode.TRANSIENT,
                f"Moltbook delete returned success but post {external_id} is still visible",
                retryable=False,
                action="RECONCILE_DELETE",
            )
        if verify.status_code in (401, 403):
            raise self._error(verify.status_code, "verify delete")
        return False

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        params: dict[str, Any] = {"sort": "new", "limit": min(max(1, int(limit)), 100)}
        if self.submolt:
            params["submolt"] = self.submolt
        if cursor:
            params["cursor"] = cursor
        response = self._http.request("GET", f"{self.base}/posts", headers=self._headers(), params=params)
        if response.status_code >= 400:
            raise self._error(response.status_code, "list posts")
        data = response.json() if response.content else {}
        rows = data.get("posts") or data.get("items") or data.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("posts") or []
        items: list[RemoteItem] = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            items.append(
                RemoteItem(
                    platform="moltbook",
                    external_id=str(row.get("id")),
                    url=str(row.get("url") or ""),
                    title=str(row.get("title") or ""),
                    description=str(row.get("content") or ""),
                    published_at=str(row.get("created_at") or row.get("published_at") or "") or None,
                    status="published",
                    media_type="text",
                    raw=row,
                )
            )
        next_cursor = None
        pagination = data.get("pagination") if isinstance(data, dict) else None
        if isinstance(pagination, dict):
            next_cursor = str(pagination.get("next_cursor") or pagination.get("next") or "") or None
        else:
            next_cursor = str(data.get("next_cursor") or "") or None if isinstance(data, dict) else None
        return RemotePage(items=items, next_cursor=next_cursor)


def create_module(**deps: Any) -> MoltbookModule:
    return MoltbookModule(**deps)
