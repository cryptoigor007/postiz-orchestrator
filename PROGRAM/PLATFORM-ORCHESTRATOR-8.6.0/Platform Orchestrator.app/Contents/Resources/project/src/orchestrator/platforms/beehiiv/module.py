from __future__ import annotations

import logging

import os
from pathlib import Path
from typing import Any

from ..base import (
    AuthStatus,
    ModuleError,
    ModuleErrorCode,
    PlatformModule,
    PublishMeta,
    PublishResult,
    PublishStatus,
    RemoteItem,
    RemotePage,
)
from ..manifest import ModuleManifest, load_manifest
from ..messaging_http import resolve_token

_MANIFEST = Path(__file__).with_name("manifest.yaml")


logger = logging.getLogger(__name__)

class BeehiivModule(PlatformModule):
    """Native beehiiv v2 publication/post API adapter.

    Post creation is asynchronous: POST returns a stable post id while the post is
    still being created. Status is therefore resolved through GET /posts/{postId}.
    """

    def __init__(self, *, token_provider=None, http=None, account_id: str = "", dry_run: bool = False,
                 publication_id: str = "", **_: Any) -> None:
        self.manifest: ModuleManifest = load_manifest(_MANIFEST)
        self._token_provider = token_provider
        self._account_id = str(account_id or os.getenv("BEEHIIV_ACCOUNT_ID", "")).strip()
        self._publication_id = str(publication_id or os.getenv("BEEHIIV_PUBLICATION_ID", "")).strip()
        self._dry_run = bool(dry_run)
        from ...http_client import ModuleHttpClient
        self._http = http or ModuleHttpClient(platform="beehiiv", module_version=self.manifest.module_version)
        self._base = "https://api.beehiiv.com/v2"

    def _token(self) -> str:
        return resolve_token(self._token_provider, "beehiiv", self._account_id)

    def _require_config(self) -> tuple[str, str]:
        token = self._token()
        if not token:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "beehiiv: BEEHIIV_API_KEY is not configured")
        if not self._publication_id:
            raise ModuleError(ModuleErrorCode.FATAL, "beehiiv: BEEHIIV_PUBLICATION_ID is required")
        return token, self._publication_id

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_id or self._publication_id or "beehiiv", details="dry-run")
        try:
            token, pub = self._require_config()
            r = self._http.request(
                "GET", f"{self._base}/publications/{pub}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code >= 400:
                body = (getattr(r, "text", "") or "")[:500]
                code = ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401, 403) else (
                    ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.FATAL
                )
                raise ModuleError(code, f"beehiiv: HTTP {r.status_code}: {body}", retryable=r.status_code in (429, 500, 502, 503, 504))
            data = r.json().get("data") or {}
            return AuthStatus(ok=True, account=str(data.get("name") or pub), details="publication ok")
        except ModuleError as exc:
            return AuthStatus(ok=False, account=self._account_id or self._publication_id, details=exc.message)
        except Exception as exc:
            return AuthStatus(ok=False, account=self._account_id or self._publication_id, details=f"{type(exc).__name__}: {exc}")

    def publish(self, media, meta: PublishMeta) -> PublishResult:
        if self._dry_run:
            return PublishResult(external_id="dry-beehiiv", url="", state="processing")
        token, pub = self._require_config()
        extra = dict(meta.extra or {})
        title = str(extra.get("beehiiv_title") or meta.title or "Untitled")
        body = str(extra.get("body_content") or extra.get("html") or meta.description or "")
        if not body.strip():
            body = title
        payload: dict[str, Any] = {
            "title": title,
            "body_content": body,
            # Since 2026-08-06 an explicit status is required to request immediate publication.
            "status": str(extra.get("status") or "confirmed"),
        }
        for key in ("subtitle", "subject_line", "preview_text", "slug", "audience", "displayed_on_web"):
            if key in extra:
                payload[key] = extra[key]
        r = self._http.request(
            "POST", f"{self._base}/publications/{pub}/posts",
            headers={"Authorization": f"Bearer {token}"}, json=payload, idempotent=False,
        )
        if r.status_code >= 400:
            body_text = (getattr(r, "text", "") or "")[:1000]
            code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else (
                ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401, 403) else ModuleErrorCode.FATAL
            )
            raise ModuleError(code, f"beehiiv: HTTP {r.status_code}: {body_text}", retryable=r.status_code in (429, 500, 502, 503, 504))
        data = r.json().get("data") or {}
        post_id = str(data.get("id") or "")
        if not post_id:
            raise ModuleError(ModuleErrorCode.FATAL, "beehiiv: create post returned no post id")
        preview = str(data.get("preview_url") or "")
        return PublishResult(external_id=post_id, url=preview, state="processing")


    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        if self._dry_run:
            return True
        token, pub = self._require_config()
        extra = dict(patch.extra or {})
        payload: dict[str, Any] = {}
        if patch.title:
            payload["title"] = patch.title
        if patch.description:
            payload["body_content"] = patch.description
        for key in ("subtitle", "subject_line", "preview_text", "slug", "audience", "status", "scheduled_at", "thumbnail_image_url", "content_tags"):
            if key in extra:
                payload[key] = extra[key]
        if not payload:
            return True
        r = self._http.request(
            "PATCH", f"{self._base}/publications/{pub}/posts/{str(external_id).strip()}",
            headers={"Authorization": f"Bearer {token}"}, json=payload, idempotent=True,
        )
        if r.status_code >= 400:
            code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else (ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.FATAL)
            raise ModuleError(code, f"beehiiv: PATCH HTTP {r.status_code}: {(getattr(r,'text','') or '')[:500]}", retryable=r.status_code in (429,500,502,503,504))
        return True

    def delete(self, external_id: str) -> bool:
        if self._dry_run:
            return True
        token, pub = self._require_config()
        r = self._http.request(
            "DELETE", f"{self._base}/publications/{pub}/posts/{str(external_id).strip()}",
            headers={"Authorization": f"Bearer {token}"}, json={}, idempotent=True,
        )
        if r.status_code in (200,202,204):
            return True
        if r.status_code == 404:
            return True
        code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else (ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.FATAL)
        raise ModuleError(code, f"beehiiv: DELETE HTTP {r.status_code}", retryable=r.status_code in (429,500,502,503,504))

    def get_status(self, external_id: str) -> PublishStatus:
        if self._dry_run:
            return PublishStatus(state="published", url="")
        token, pub = self._require_config()
        r = self._http.request(
            "GET", f"{self._base}/publications/{pub}/posts/{str(external_id).strip()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code == 202:
            return PublishStatus(state="processing", url="")
        if r.status_code == 404:
            return PublishStatus(state="failed", url="", error="POST_CREATION_FAILED")
        if r.status_code >= 400:
            code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else (
                ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401, 403) else ModuleErrorCode.FATAL
            )
            raise ModuleError(code, f"beehiiv: HTTP {r.status_code}", retryable=r.status_code in (429, 500, 502, 503, 504))
        data = r.json().get("data") or {}
        status = str(data.get("status") or "draft").lower()
        mapped = "published" if status in {"confirmed", "published"} else ("failed" if status in {"failed", "post_creation_failed"} else status)
        return PublishStatus(state=mapped, url=str(data.get("web_url") or data.get("preview_url") or ""), raw=data)

    def list_remote_items(self, *, kinds: set[str] | None = None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        if self._dry_run:
            return RemotePage(items=[])
        token, pub = self._require_config()
        params = {"limit": min(max(1, int(limit)), 100), "page": 1}
        if cursor:
            try:
                params["page"] = max(1, int(cursor))
            except ValueError:
                logger.warning("beehiiv list_remote invalid cursor: %r", cursor)
        r = self._http.request(
            "GET", f"{self._base}/publications/{pub}/posts", headers={"Authorization": f"Bearer {token}"}, params=params,
        )
        if r.status_code >= 400:
            code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.FATAL
            raise ModuleError(code, f"beehiiv: HTTP {r.status_code}", retryable=r.status_code in (429, 500, 502, 503, 504))
        data = r.json() or {}
        rows = data.get("data") or []
        items: list[RemoteItem] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "draft").lower()
            items.append(RemoteItem(
                platform="beehiiv", external_id=str(row.get("id") or ""),
                url=str(row.get("web_url") or row.get("preview_url") or ""),
                title=str(row.get("title") or ""), status=status,
            ))
        page = int(params.get("page") or 1)
        total_pages = int(data.get("total_pages") or page)
        return RemotePage(items=items, next_cursor=str(page + 1) if page < total_pages else None, partial=False)


def create_module(**deps: Any) -> BeehiivModule:
    return BeehiivModule(**deps)
