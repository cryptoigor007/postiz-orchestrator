from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import logging
import os

import httpx

from .postiz import PostizPost

logger = logging.getLogger(__name__)

def _request_with_retry(client: httpx.Client, method: str, url: str, retries: int = 3, **kwargs):
    last = None
    for i in range(retries):
        try:
            r = client.request(method, url, **kwargs)
            if r.status_code >= 500:
                raise httpx.HTTPStatusError("server error", request=r.request, response=r)
            return r
        except Exception as e:
            last = e
            import time
            time.sleep(1.5 * (i + 1))
    raise last



def _first(data: dict, *keys: str, default=None):
    for k in keys:
        if k in data and data[k] is not None:
            return data[k]
    return default


class HttpPostizClient:
    """Real Postiz API client with flexible JSON fields and path overrides."""

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 60.0):
        self.base_url = (base_url or os.getenv("POSTIZ_BASE_URL", "http://localhost:5000")).rstrip("/")
        self.token = token or os.getenv("POSTIZ_API_TOKEN", "")
        self.path_upload = os.getenv("POSTIZ_PATH_UPLOAD", "/api/media/upload")
        self.path_posts = os.getenv("POSTIZ_PATH_POSTS", "/api/posts")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
            timeout=timeout,
        )
        self._orphan_media: list[str] = []

    def close(self) -> None:
        self._client.close()

    def upload_media(self, path: str, platform: str) -> str:
        with open(path, "rb") as f:
            r = _request_with_retry(self._client, "POST", self.path_upload,
                files={"file": (path.split("/")[-1], f)},
                data={"platform": platform},
            )
        r.raise_for_status()
        data = r.json()
        mid = _first(data, "id", "mediaId", "media_id", "path")
        if not mid:
            raise RuntimeError(f"upload: no media id in {data}")
        return str(mid)

    def create_post(self, platform: str, media_id: str, content: dict[str, Any],
                    scheduled_for: datetime | None = None) -> PostizPost:
        body: dict[str, Any] = {
            "platform": platform,
            "mediaId": media_id,
            "media_id": media_id,
            "title": content.get("title", ""),
            "description": content.get("description", ""),
            "hashtags": content.get("hashtags", ""),
        }
        if scheduled_for:
            if scheduled_for.tzinfo is None:
                scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)
            iso = scheduled_for.isoformat()
            body["scheduledFor"] = iso
            body["scheduled_for"] = iso
        try:
            r = _request_with_retry(self._client, "POST", self.path_posts, json=body)
            r.raise_for_status()
        except Exception:
            self._orphan_media.append(media_id)
            logger.error("CREATE failed, orphan media_id=%s", media_id)
            raise
        data = r.json()
        pid = _first(data, "id", "postId", "post_id")
        if not pid:
            raise RuntimeError(f"create: no post id in {data}")
        return PostizPost(
            id=str(pid), platform=platform, scheduled_for=scheduled_for,
            status=_first(data, "status", default="scheduled"),
            release_url=_first(data, "releaseUrl", "release_url", "url"),
            content=content,
        )

    def delete_post(self, post_id: str) -> None:
        r = self._client.delete(f"{self.path_posts}/{post_id}")
        if r.status_code not in (200, 204, 404):
            r.raise_for_status()

    def get_post(self, post_id: str) -> PostizPost | None:
        r = self._client.get(f"{self.path_posts}/{post_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        sched = _first(data, "scheduledFor", "scheduled_for")
        return PostizPost(
            id=str(_first(data, "id", "postId")),
            platform=_first(data, "platform", default=""),
            scheduled_for=datetime.fromisoformat(sched) if sched else None,
            status=_first(data, "status", default="unknown"),
            release_url=_first(data, "releaseUrl", "release_url", "url"),
            content=data.get("content"),
        )

    def list_scheduled(self, platform: str | None = None) -> list[PostizPost]:
        params: dict[str, str] = {"status": "scheduled"}
        if platform:
            params["platform"] = platform
        r = self._client.get(self.path_posts, params=params)
        r.raise_for_status()
        payload = r.json()
        items = payload if isinstance(payload, list) else (
            payload.get("items") or payload.get("data") or payload.get("posts") or []
        )
        result = []
        for data in items:
            sched = _first(data, "scheduledFor", "scheduled_for")
            result.append(PostizPost(
                id=str(_first(data, "id", "postId")),
                platform=_first(data, "platform", default=""),
                scheduled_for=datetime.fromisoformat(sched) if sched else None,
                status=_first(data, "status", default="scheduled"),
                release_url=_first(data, "releaseUrl", "release_url", "url"),
            ))
        return result

    def orphan_media_ids(self) -> list[str]:
        return list(self._orphan_media)

    def clear_orphan_media(self) -> list[str]:
        out = list(self._orphan_media)
        self._orphan_media.clear()
        return out
