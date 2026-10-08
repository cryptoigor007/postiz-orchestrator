"""Facebook Graph Page — Reels/Video + schedule + list partial."""
from __future__ import annotations

import logging
import os
from typing import Any

from ...http_client import ModuleHttpClient, mask_secrets
from ..base import ModuleError, ModuleErrorCode
from ..errors import message_for

logger = logging.getLogger(__name__)


def graph_base(version: str | None = None) -> str:
    ver = (version or os.getenv("META_GRAPH_VERSION") or "v26.0").strip()
    if not ver.startswith("v"):
        ver = f"v{ver}"
    return f"https://graph.facebook.com/{ver}"


def _map(status: int, body: str) -> ModuleError:
    t = (body or "").lower()
    d = mask_secrets((body or "")[:300])
    if status in (401, 190) or "session" in t:
        m, a = message_for(ModuleErrorCode.AUTH_EXPIRED, d)
        return ModuleError(ModuleErrorCode.AUTH_EXPIRED, m, action=a)
    if status == 429:
        m, a = message_for(ModuleErrorCode.RATE_LIMIT, d)
        return ModuleError(ModuleErrorCode.RATE_LIMIT, m, action=a, retryable=True)
    if status >= 500:
        m, a = message_for(ModuleErrorCode.TRANSIENT, f"HTTP {status}")
        return ModuleError(ModuleErrorCode.TRANSIENT, m, action=a, retryable=True)
    m, a = message_for(ModuleErrorCode.PLATFORM_REJECTED, d)
    return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, m, action=a)


class FacebookApi:
    def __init__(
        self,
        page_token: str,
        page_id: str,
        *,
        http: ModuleHttpClient | None = None,
        dry_run: bool = False,
        graph_version: str | None = None,
    ):
        self.token = (page_token or "").strip()
        self.page_id = (page_id or "").strip()
        self.dry_run = dry_run
        self._base = graph_base(graph_version)
        self._http = http or ModuleHttpClient(platform="facebook", module_version="0.3.0")
        self._n = 0

    def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        if self.dry_run:
            self._n += 1
            return {"id": f"fb-dry-{self._n}", "permalink_url": f"https://facebook.com/dry/{self._n}"}
        data = {**data, "access_token": self.token}
        resp = self._http.request("POST", f"{self._base}/{path.lstrip('/')}", data=data)
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {}
        if resp.status_code >= 400 or (isinstance(body, dict) and body.get("error")):
            err = (body or {}).get("error") or {}
            raise _map(resp.status_code, str(err.get("message") or body or resp.text))
        return body if isinstance(body, dict) else {}

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        if self.dry_run:
            return {"id": self.page_id, "name": "dry_page", "data": []}
        p = {**(params or {}), "access_token": self.token}
        resp = self._http.request("GET", f"{self._base}/{path.lstrip('/')}", params=p)
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {}
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        return body if isinstance(body, dict) else {}

    def page_info(self) -> dict[str, Any]:
        return self._get(self.page_id, {"fields": "id,name"})

    def feed_post(self, message: str, link: str = "") -> str:
        data: dict[str, Any] = {"message": message[:5000]}
        if link:
            data["link"] = link
        res = self._post(f"{self.page_id}/feed", data)
        return str(res.get("id") or "")

    def video_post(
        self,
        file_url: str,
        description: str = "",
        *,
        title: str = "",
        scheduled_publish_time: int | None = None,
        published: bool = True,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "file_url": file_url,
            "description": description[:5000],
            "published": "true" if published else "false",
        }
        if title:
            data["title"] = title[:255]
        if scheduled_publish_time:
            data["scheduled_publish_time"] = str(int(scheduled_publish_time))
            data["published"] = "false"
        return self._post(f"{self.page_id}/videos", data)

    def reels_post(self, file_url: str, description: str = "") -> dict[str, Any]:
        # Page video with reel-ish description; Graph reels endpoint varies by app review
        return self.video_post(file_url, description=description)

    def get_video(self, object_id: str) -> dict[str, Any]:
        return self._get(object_id, {"fields":"id,status,permalink_url,published,scheduled_publish_time,description,title,created_time,updated_time"})

    def update_video(self, object_id: str, *, description: str | None = None, title: str | None = None) -> bool:
        data: dict[str, Any] = {}
        if description is not None: data["description"] = description[:5000]
        if title is not None: data["title"] = title[:255]
        if not data:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Facebook: no supported metadata fields supplied")
        self._post(object_id, data)
        return True

    def permalink(self, object_id: str) -> str:
        if self.dry_run:
            return f"https://www.facebook.com/{object_id}"
        body = self._get(object_id, {"fields": "permalink_url,id"})
        return str(body.get("permalink_url") or f"https://www.facebook.com/{object_id}")

    def list_videos(self, limit: int = 25) -> list[dict[str, Any]]:
        body = self._get(f"{self.page_id}/videos", {"fields": "id,title,created_time,permalink_url", "limit": str(limit)})
        return list(body.get("data") or [])

    def list_scheduled_posts(self, limit: int = 25) -> list[dict[str, Any]]:
        # partial: unpublished page posts
        body = self._get(
            f"{self.page_id}/scheduled_posts",
            {"fields": "id,message,scheduled_publish_time", "limit": str(limit)},
        )
        return list(body.get("data") or [])

    def delete(self, object_id: str) -> bool:
        if self.dry_run:
            return True
        resp = self._http.request(
            "DELETE", f"{self._base}/{object_id}", params={"access_token": self.token},
        )
        return resp.status_code < 400
