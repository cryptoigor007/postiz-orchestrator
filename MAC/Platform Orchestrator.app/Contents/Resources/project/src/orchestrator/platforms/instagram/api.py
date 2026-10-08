"""Instagram Graph API client (Content Publishing) — injectable HTTP.

Live: graph.facebook.com. Dry-run / unit без ключей.
См. docs/modules/MODULE_INSTAGRAM.txt.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ...http_client import ModuleHttpClient, mask_secrets
from ..base import ModuleError, ModuleErrorCode
from ..errors import message_for

logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v26.0"


def _map_ig(status: int, body: str) -> ModuleError:
    t = (body or "").lower()
    d = mask_secrets((body or "")[:300])
    if status in (401, 190) or "session has expired" in t or "invalid oauth" in t:
        msg, act = message_for(ModuleErrorCode.AUTH_EXPIRED, d)
        return ModuleError(ModuleErrorCode.AUTH_EXPIRED, msg, action=act)
    if status == 403 or "permission" in t:
        msg, act = message_for(ModuleErrorCode.AUTH_REQUIRED, d)
        return ModuleError(ModuleErrorCode.AUTH_REQUIRED, msg, action=act)
    if status == 429 or "rate limit" in t:
        msg, act = message_for(ModuleErrorCode.RATE_LIMIT, d)
        return ModuleError(ModuleErrorCode.RATE_LIMIT, msg, action=act, retryable=True)
    if status >= 500:
        msg, act = message_for(ModuleErrorCode.TRANSIENT, f"HTTP {status}")
        return ModuleError(ModuleErrorCode.TRANSIENT, msg, action=act, retryable=True)
    if "expired" in t and "container" in t:
        msg, act = message_for(ModuleErrorCode.MEDIA_INVALID, "контейнер IG истёк (TTL ~24ч)")
        return ModuleError(ModuleErrorCode.MEDIA_INVALID, msg, action=act)
    msg, act = message_for(ModuleErrorCode.PLATFORM_REJECTED, d)
    return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, msg, action=act)


class InstagramApi:
    def __init__(
        self,
        access_token: str,
        ig_user_id: str,
        *,
        http: ModuleHttpClient | None = None,
        dry_run: bool = False,
    ) -> None:
        self.token = (access_token or "").strip()
        self.ig_user_id = (ig_user_id or "").strip()
        self.dry_run = bool(dry_run)
        self._http = http or ModuleHttpClient(platform="instagram", module_version="0.2.0")
        self._n = 0

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.dry_run:
            return {"id": self.ig_user_id or "ig-dry", "username": "dry_ig"}
        p = dict(params or {})
        p["access_token"] = self.token
        url = f"{GRAPH}/{path.lstrip('/')}"
        resp = self._http.request("GET", url, params=p)
        return self._parse(resp)

    def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        if self.dry_run:
            self._n += 1
            if "media_publish" in path:
                return {"id": f"media-pub-{self._n}"}
            return {"id": f"container-{self._n}"}
        payload = dict(data)
        payload["access_token"] = self.token
        url = f"{GRAPH}/{path.lstrip('/')}"
        resp = self._http.request("POST", url, data=payload)
        return self._parse(resp)

    def _parse(self, resp: httpx.Response) -> dict[str, Any]:
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {}
        if resp.status_code >= 400 or (isinstance(body, dict) and body.get("error")):
            err = body.get("error") if isinstance(body, dict) else {}
            desc = str((err or {}).get("message") or body or resp.text)[:400]
            raise _map_ig(resp.status_code, desc)
        return body if isinstance(body, dict) else {}

    def me(self) -> dict[str, Any]:
        if not self.ig_user_id:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                "ig_user_id не задан",
                action="подключите IG через OAuth / токен-брокер",
            )
        return self._get(self.ig_user_id, {"fields": "id,username"})

    def create_reels_container(self, video_url: str, caption: str = "") -> str:
        """POST /{ig-user-id}/media media_type=REELS + video_url."""
        if not video_url and not self.dry_run:
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                "нужен публичный video_url (B2)",
                action="загрузите файл в media_host и передайте URL",
            )
        data = {
            "media_type": "REELS",
            "video_url": video_url or "https://example.invalid/dry.mp4",
            "caption": (caption or "")[:2200],
        }
        res = self._post(f"{self.ig_user_id}/media", data)
        cid = str(res.get("id") or "")
        if not cid:
            raise ModuleError(ModuleErrorCode.FATAL, "IG не вернул container id", action="логи")
        return cid

    def create_image_container(self, image_url: str, caption: str = "") -> str:
        if not image_url and not self.dry_run:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "нужен публичный image_url")
        res = self._post(f"{self.ig_user_id}/media", {"image_url": image_url or "https://example.invalid/dry.jpg", "caption": (caption or "")[:2200], "media_type":"IMAGE"})
        cid = str(res.get("id") or "")
        if not cid:
            raise ModuleError(ModuleErrorCode.FATAL, "IG не вернул image container id")
        return cid

    def create_carousel_container(self, child_ids: list[str], caption: str = "") -> str:
        if len(child_ids) < 2 or len(child_ids) > 10:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Instagram carousel requires 2..10 child containers")
        res = self._post(f"{self.ig_user_id}/media", {"media_type":"CAROUSEL", "children":",".join(child_ids), "caption":(caption or "")[:2200]})
        cid = str(res.get("id") or "")
        if not cid:
            raise ModuleError(ModuleErrorCode.FATAL, "IG не вернул carousel container id")
        return cid

    def list_media(self, limit: int = 25) -> list[dict[str, Any]]:
        if self.dry_run:
            return []
        return list(self._get(f"{self.ig_user_id}/media", {"fields":"id,permalink,caption,media_type,media_product_type,timestamp", "limit":str(limit)}).get("data") or [])

    def container_status(self, container_id: str) -> str:
        if self.dry_run:
            return "FINISHED"
        res = self._get(container_id, {"fields": "status_code"})
        return str(res.get("status_code") or "UNKNOWN")

    def publish_container(self, container_id: str) -> str:
        res = self._post(f"{self.ig_user_id}/media_publish", {"creation_id": container_id})
        mid = str(res.get("id") or "")
        if not mid:
            raise ModuleError(ModuleErrorCode.FATAL, "IG media_publish без id", action="логи")
        return mid

    def permalink(self, media_id: str) -> str:
        if self.dry_run:
            return f"https://www.instagram.com/reel/dry-{media_id}/"
        res = self._get(media_id, {"fields": "permalink"})
        return str(res.get("permalink") or "")
