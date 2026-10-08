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
from ...http_client import ModuleHttpClient
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class DevtoModule(PlatformModule):
    """Forem/DEV API v1 adapter for article publishing and reconciliation."""

    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base_url = str(deps.get("base_url") or os.getenv("DEVTO_BASE_URL", "https://dev.to/api")).rstrip("/")
        self.api_key = str(deps.get("api_key") or os.getenv("DEVTO_API_KEY", "")).strip()
        self._http = deps.get("http") or ModuleHttpClient(platform="devto", module_version=self.manifest.module_version)

    def _headers(self) -> dict[str, str]:
        return {"api-key": self.api_key, "Content-Type": "application/json"}

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
        return ModuleError(code, f"Dev.to {operation} HTTP {status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def auth_status(self) -> AuthStatus:
        if not self.api_key:
            return AuthStatus(False, account="dev.to", details="DEVTO_API_KEY missing")
        response = self._http.request("GET", f"{self.base_url}/users/me", headers={"api-key": self.api_key})
        if response.status_code >= 400:
            return AuthStatus(False, account="dev.to", details=f"HTTP {response.status_code}")
        data = response.json() if response.content else {}
        return AuthStatus(True, account=str(data.get("username") or data.get("name") or "dev.to"), details="users/me ok")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        return ["devto: DEVTO_API_KEY is required"] if not self.api_key else []

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path, kind=media.kind or "text")

    def _article_payload(self, media: PreparedMedia, meta: PublishMeta) -> dict[str, Any]:
        extra = dict(meta.extra or {})
        title = str(extra.get("title") or meta.title or Path(media.path).stem or "Untitled")
        body = str(extra.get("body_markdown") or meta.description or "")
        payload: dict[str, Any] = {
            "title": title,
            "body_markdown": body,
            "published": bool(extra.get("published", True)),
        }
        tags = extra.get("tags") or meta.hashtags
        if tags:
            values = tags.split(",") if isinstance(tags, str) and "," in tags else str(tags).replace("#", " ").split()
            payload["tags"] = ",".join(v.strip().lstrip("#") for v in values if v.strip())[:500]
        for key in ("series", "main_image", "canonical_url", "description", "organization_id"):
            if extra.get(key) not in (None, ""):
                payload[key] = extra[key]
        return payload

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if not self.api_key:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Dev.to: DEVTO_API_KEY missing")
        article = self._article_payload(media, meta)
        if not article["body_markdown"]:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Dev.to: body_markdown is empty")
        response = self._http.request(
            "POST", f"{self.base_url}/articles", headers=self._headers(), json={"article": article}, idempotent=False
        )
        if response.status_code >= 400:
            raise self._error(response.status_code, "create article")
        data = response.json() if response.content else {}
        external_id = str(data.get("id") or "")
        if not external_id:
            raise ModuleError(ModuleErrorCode.FATAL, "Dev.to: article create without id")
        return PublishResult(
            external_id=external_id,
            url=str(data.get("url") or ""),
            state="published" if article["published"] else "uploaded",
        )

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        if not self.api_key:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Dev.to: DEVTO_API_KEY missing")
        payload = {"article": self._article_payload(PreparedMedia(path="", kind="text"), patch)}
        if not payload["article"]["body_markdown"]:
            payload["article"].pop("body_markdown", None)
        response = self._http.request(
            "PUT", f"{self.base_url}/articles/{external_id}", headers=self._headers(), json=payload, idempotent=False
        )
        if response.status_code >= 400:
            raise self._error(response.status_code, "update article")
        return True

    def get_status(self, external_id: str) -> PublishStatus:
        response = self._http.request("GET", f"{self.base_url}/articles/{external_id}", headers={"api-key": self.api_key})
        if response.status_code == 404:
            return PublishStatus(state="deleted")
        if response.status_code >= 400:
            raise self._error(response.status_code, "get article")
        data = response.json() if response.content else {}
        # Forem documents /articles/{id} as the published-article lookup endpoint.
        # A successful response therefore represents a published remote item.
        return PublishStatus(state="published", url=str(data.get("url") or ""), raw=data)

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        params = {"page": int(cursor or 1), "per_page": min(max(1, int(limit)), 1000)}
        response = self._http.request("GET", f"{self.base_url}/articles/me/all", headers={"api-key": self.api_key}, params=params)
        if response.status_code >= 400:
            raise self._error(response.status_code, "list articles")
        rows = response.json() if response.content else []
        if not isinstance(rows, list):
            rows = []
        items = [
            RemoteItem(
                platform="devto",
                external_id=str(row.get("id") or ""),
                url=str(row.get("url") or ""),
                title=str(row.get("title") or ""),
                description=str(row.get("description") or ""),
                published_at=str(row.get("published_at") or row.get("published_timestamp") or "") or None,
                status="published" if row.get("published_at") or row.get("published_timestamp") else "private",
                media_type="text",
                raw=row,
            )
            for row in rows
            if isinstance(row, dict) and row.get("id")
        ]
        next_cursor = str(int(params["page"]) + 1) if len(rows) >= params["per_page"] else None
        return RemotePage(items=items, next_cursor=next_cursor)


def create_module(**deps: Any) -> DevtoModule:
    return DevtoModule(**deps)
