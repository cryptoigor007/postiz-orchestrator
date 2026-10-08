from __future__ import annotations

import logging

import os
import time
from pathlib import Path
from typing import Any

from ..base import AuthStatus, ModuleError, ModuleErrorCode, PlatformModule, PreparedMedia, MediaSpec, PublishMeta, PublishResult, PublishStatus, RemoteItem, RemotePage
from ...http_client import ModuleHttpClient
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")


logger = logging.getLogger(__name__)

class LemmyModule(PlatformModule):
    """Native Lemmy REST module for text posts on a configured community."""

    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base_url = str(deps.get("base_url") or os.getenv("LEMMY_BASE_URL", "")).rstrip("/")
        self.username = str(deps.get("username") or os.getenv("LEMMY_USERNAME", "")).strip()
        self.password = str(deps.get("password") or os.getenv("LEMMY_PASSWORD", ""))
        self.community_id = int(deps.get("community_id") or os.getenv("LEMMY_COMMUNITY_ID", "0") or 0)
        self._http = deps.get("http") or ModuleHttpClient(platform="lemmy", module_version=self.manifest.module_version)
        self._jwt = ""
        self._jwt_at = 0.0

    def _login(self, force: bool = False) -> str:
        if self._jwt and not force and time.time() - self._jwt_at < 300:
            return self._jwt
        if not self.base_url or not self.username or not self.password:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Lemmy: LEMMY_BASE_URL/USERNAME/PASSWORD are required")
        r = self._http.request(
            "POST",
            f"{self.base_url}/api/v3/user/login",
            json={"username_or_email": self.username, "password": self.password},
            idempotent=False,
        )
        if r.status_code >= 400:
            code = ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL
            raise ModuleError(code, f"Lemmy login HTTP {r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})
        d = r.json() if r.content else {}
        jwt = str(d.get("jwt") or "")
        if not jwt:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, f"Lemmy login failed: {d.get('registration_created') or 'no jwt'}")
        self._jwt = jwt
        self._jwt_at = time.time()
        return jwt

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._login()}"}

    def auth_status(self) -> AuthStatus:
        try:
            jwt = self._login()
            r = self._http.request("GET", f"{self.base_url}/api/v3/site", headers={"Authorization": f"Bearer {jwt}"})
            if r.status_code >= 400:
                return AuthStatus(False, account=self.username, details=f"site HTTP {r.status_code}")
            d = r.json() if r.content else {}
            site = (d.get("site") or {}).get("name") or self.base_url
            return AuthStatus(True, account=self.username, details=f"server={site}")
        except ModuleError as exc:
            return AuthStatus(False, account=self.username or self.base_url, details=exc.message)

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        if not self.base_url: errs.append("lemmy: LEMMY_BASE_URL is required")
        if not self.username: errs.append("lemmy: LEMMY_USERNAME is required")
        if not self.password: errs.append("lemmy: LEMMY_PASSWORD is required")
        if self.community_id <= 0: errs.append("lemmy: LEMMY_COMMUNITY_ID must be a positive integer")
        return errs

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path, kind="text")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if self.community_id <= 0:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Lemmy: community_id is required")
        body = str((meta.extra or {}).get("body") or meta.description or "").strip()
        title = str(meta.title or "").strip() or Path(media.path).stem or "VideoMaker post"
        payload: dict[str, Any] = {"name": title, "community_id": self.community_id, "auth": self._login()}
        if body:
            payload["body"] = body
        url = str((meta.extra or {}).get("url") or "").strip()
        if url:
            payload["url"] = url
        language_id = (meta.extra or {}).get("language_id")
        if language_id is not None:
            payload["language_id"] = int(language_id)
        r = self._http.request("POST", f"{self.base_url}/api/v3/post", json=payload, idempotent=False)
        if r.status_code >= 400:
            code = ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.PLATFORM_REJECTED if r.status_code in (400,422) else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL
            raise ModuleError(code, f"Lemmy post HTTP {r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})
        d = r.json() if r.content else {}
        pv = d.get("post_view") or {}
        post = pv.get("post") or {}
        pid = str(post.get("id") or "")
        if not pid:
            raise ModuleError(ModuleErrorCode.FATAL, "Lemmy: post create without id")
        return PublishResult(external_id=pid, url=str(post.get("ap_id") or post.get("url") or ""), state="published")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        payload: dict[str, Any] = {"id": int(external_id), "auth": self._login()}
        if patch.title:
            payload["name"] = str(patch.title)
        if patch.description:
            payload["body"] = str(patch.description)
        extra = dict(patch.extra or {})
        if extra.get("url") is not None:
            payload["url"] = str(extra["url"])
        if extra.get("nsfw") is not None:
            payload["nsfw"] = bool(extra["nsfw"])
        if extra.get("language_id") is not None:
            payload["language_id"] = int(extra["language_id"])
        if len(payload) == 2:  # id + auth only
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Lemmy: update patch is empty")
        r = self._http.request("PUT", f"{self.base_url}/api/v3/post", json=payload, idempotent=False)
        if r.status_code >= 400:
            code = ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401, 403) else ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.PLATFORM_REJECTED if r.status_code in (400, 404, 422) else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL
            raise ModuleError(code, f"Lemmy edit post HTTP {r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})
        return True

    def get_status(self, external_id: str) -> PublishStatus:
        r = self._http.request("GET", f"{self.base_url}/api/v3/post", params={"id": int(external_id)}, headers=self._headers())
        if r.status_code == 404:
            return PublishStatus(state="deleted")
        if r.status_code >= 400:
            raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL, f"Lemmy get post HTTP {r.status_code}", retryable=r.status_code >= 500)
        d = r.json() if r.content else {}
        pv = d.get("post_view") or {}
        if not pv:
            return PublishStatus(state="deleted")
        post = pv.get("post") or {}
        if post.get("deleted") or post.get("removed"):
            return PublishStatus(state="deleted", raw=post)
        return PublishStatus(state="published", url=str(post.get("ap_id") or post.get("url") or ""), raw=pv)

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        params: dict[str, Any] = {"community_id": self.community_id, "limit": min(max(int(limit), 1), 50), "type_": "All"}
        if cursor:
            try:
                params["page_cursor"] = cursor
            except Exception as exc:
                logger.warning("Lemmy invalid page cursor: %s", type(exc).__name__)
        r = self._http.request("GET", f"{self.base_url}/api/v3/post/list", params=params, headers=self._headers())
        if r.status_code >= 400:
            code = ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401, 403) else ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL
            raise ModuleError(code, f"Lemmy list posts HTTP {r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})
        d = r.json() if r.content else {}
        rows = d.get("posts") or []
        items: list[Any] = []
        for pv in rows:
            post = (pv or {}).get("post") or {}
            if not post or post.get("deleted") or post.get("removed"):
                continue
            items.append(
                RemoteItem(
                    platform="lemmy",
                    external_id=str(post.get("id") or ""),
                    url=str(post.get("ap_id") or post.get("url") or ""),
                    title=str(post.get("name") or ""),
                    description=str(post.get("body") or ""),
                    published_at=str(post.get("published") or "") or None,
                    status="published",
                    media_type="text" if not post.get("url") else "text",
                    raw=pv,
                )
            )
        return RemotePage(items=items, next_cursor=str(d.get("next_page") or "") or None)

    def delete(self, external_id: str) -> bool:
        r = self._http.request("POST", f"{self.base_url}/api/v3/post/delete", json={"post_id": int(external_id), "deleted": True, "auth": self._login()}, idempotent=False)
        if r.status_code >= 400:
            raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL, f"Lemmy delete HTTP {r.status_code}", retryable=r.status_code >= 500)
        return True


def create_module(**deps: Any) -> LemmyModule:
    return LemmyModule(**deps)
