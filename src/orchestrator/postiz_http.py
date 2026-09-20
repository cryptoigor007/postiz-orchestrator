from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from .postiz import MediaRef, PostizPost

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


def _upload_path(data: dict) -> str | None:
    return _first(data, "path", "url")


class HttpPostizClient:
    """
    Postiz public API v1 (confirmed):
      Authorization: <api_key>   # NO "Bearer"
      POST   /public/v1/upload
      POST   /public/v1/posts
      GET    /public/v1/posts?startDate=&endDate=
      DELETE /public/v1/posts/{id}
      PUT    /public/v1/posts/{id}/status
      PUT    /public/v1/posts/{id}/release-id
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        verify: bool | None = None,
    ):
        self.base_url = (base_url or os.getenv("POSTIZ_BASE_URL", "http://localhost:5000")).rstrip("/")
        self.token = token or os.getenv("POSTIZ_API_TOKEN", "")
        self.path_upload = os.getenv("POSTIZ_PATH_UPLOAD", "/public/v1/upload")
        self.path_posts = os.getenv("POSTIZ_PATH_POSTS", "/public/v1/posts")
        if verify is None:
            verify = os.getenv("POSTIZ_VERIFY_TLS", "0").strip().lower() in (
                "1", "true", "yes", "on",
            )
        self.verify_tls = verify
        # Real Postiz: Authorization is raw key, not Bearer
        auth_style = os.getenv("POSTIZ_AUTH_STYLE", "raw").lower()  # raw | bearer
        if self.token:
            header = f"Bearer {self.token}" if auth_style == "bearer" else self.token
            headers = {"Authorization": header}
        else:
            headers = {}
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            verify=verify,
            transport=transport,
        )
        self._orphan_media: list[str] = []
        # optional default integration from env
        self.default_integration_id = os.getenv("POSTIZ_INTEGRATION_ID", "").strip()

    def close(self) -> None:
        self._client.close()

    def upload_media(self, path: str, platform: str) -> MediaRef:
        with open(path, "rb") as f:
            r = _request_with_retry(
                self._client, "POST", self.path_upload,
                files={"file": (os.path.basename(path), f)},
            )
        r.raise_for_status()
        data = r.json()
        mid = _first(data, "id", "mediaId", "media_id")
        if not mid:
            raise RuntimeError(f"upload: no media id in {data}")
        mpath = _upload_path(data)
        if not mpath:
            raise RuntimeError(f"upload: no media path in {data}")
        return MediaRef(id=str(mid), path=str(mpath))

    def _platform_settings(self, platform: str, content: dict[str, Any]) -> dict[str, Any]:
        """Postiz-специфичные settings: YouTube требует title/type/madeForKids."""
        if platform != "youtube":
            return {}
        raw_title = str(content.get("title") or content.get("description") or "").strip()
        title = raw_title.splitlines()[0][:100] if raw_title else ""
        if len(title) < 2:
            title = (title + " видео")[:100]
        privacy = str(content.get("privacy") or "public")
        if privacy not in ("public", "private", "unlisted"):
            privacy = "public"
        settings: dict[str, Any] = {
            "title": title,
            "type": privacy,
            "selfDeclaredMadeForKids": "no",
        }
        tags = []
        total = 0
        for token in re.findall(r"#\S+", str(content.get("hashtags") or "")):
            label = token.lstrip("#").strip().strip(",.")
            if not label:
                continue
            add = len(label) + (2 if any(ch.isspace() for ch in label) else 0)
            if total + add > 480:
                break
            tags.append({"value": label, "label": label})
            total += add
        if tags:
            settings["tags"] = tags
        return settings

    def create_post(
        self,
        platform: str,
        media: MediaRef | str | None,
        content: dict[str, Any],
        scheduled_for: datetime | None = None,
    ) -> PostizPost:
        if media is None:
            media_ref = MediaRef(id="", path="")
        else:
            media_ref = media if isinstance(media, MediaRef) else MediaRef(id=str(media), path="")
        integration_id = (
            content.get("integration_id")
            or content.get("integrationId")
            or self.default_integration_id
        )
        if not integration_id:
            raise RuntimeError(
                "Postiz requires integrationId — set platforms.<name>.integration_id "
                "or POSTIZ_INTEGRATION_ID"
            )

        message = content.get("description") or content.get("title") or ""
        hashtags = content.get("hashtags")
        if hashtags:
            tags = hashtags if isinstance(hashtags, str) else " ".join(hashtags)
            message = f"{message} {tags}".strip()

        image = []
        if media_ref.id:
            image.append({"id": media_ref.id, "path": media_ref.path})

        # Postiz CreatePostDto: { type, shortLink, date, tags, posts:[{integration,value,settings}] }
        if scheduled_for:
            if scheduled_for.tzinfo is None:
                scheduled_for = scheduled_for.replace(tzinfo=UTC)
            post_type = content.get("post_type", "schedule")
            date = scheduled_for.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            post_type = content.get("post_type", "now")
            date = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        entry: dict[str, Any] = {
            "integration": {"id": integration_id},
            "value": [{"content": message, "image": image}],
            "settings": {**self._platform_settings(platform, content),
                         **(content.get("settings") or {})},
        }
        if content.get("group"):
            entry["group"] = content["group"]

        body: dict[str, Any] = {
            "type": post_type,
            "shortLink": False,
            "date": date,
            "tags": [],
            "posts": [entry],
        }

        try:
            r = _request_with_retry(self._client, "POST", self.path_posts, json=body)
            r.raise_for_status()
        except Exception:
            self._orphan_media.append(media_ref.id)
            logger.error("CREATE failed, orphan media_id=%s", media_ref.id)
            raise

        data = r.json()
        # response may be object or list
        if isinstance(data, list) and data:
            data = data[0]
        pid = _first(data, "id", "postId", "post_id")
        if not pid:
            raise RuntimeError(f"create: no post id in {data}")
        return PostizPost(
            id=str(pid),
            platform=platform,
            scheduled_for=scheduled_for,
            status=_first(data, "status", default="scheduled"),
            release_url=_first(data, "releaseUrl", "releaseURL", "release_url", "url", "releaseId"),
            content=content,
        )

    def delete_post(self, post_id: str) -> None:
        r = self._client.delete(f"{self.path_posts}/{post_id}")
        if r.status_code not in (200, 204, 404):
            r.raise_for_status()

    def set_status(self, post_id: str, status: str) -> None:
        r = self._client.put(f"{self.path_posts}/{post_id}/status", json={"status": status})
        if r.status_code not in (200, 204):
            r.raise_for_status()

    def set_release_id(self, post_id: str, release_id: str) -> None:
        r = self._client.put(
            f"{self.path_posts}/{post_id}/release-id",
            json={"releaseId": release_id, "release_id": release_id},
        )
        if r.status_code not in (200, 204):
            r.raise_for_status()

    def get_post(self, post_id: str) -> PostizPost | None:
        r = self._client.get(f"{self.path_posts}/{post_id}")
        if r.status_code < 400:
            data = r.json()
            if isinstance(data, list):
                data = data[0] if data else {}
            integration = data.get("integration") or {}
            sched = _first(data, "publishDate", "scheduledFor", "scheduled_for", "date")
            status = _first(data, "state", "status", default="unknown")
            return PostizPost(
                id=str(_first(data, "id", "postId") or post_id),
                platform=_first(integration, "providerIdentifier", "name",
                                "platform", default=""),
                scheduled_for=datetime.fromisoformat(sched.replace("Z", "+00:00")) if sched else None,
                status=str(status).lower(),
                release_url=_first(data, "releaseURL", "releaseUrl", "release_url", "url", "releaseId"),
                content=({"text": data["content"]} if data.get("content") else None),
            )
        # этот Postiz может не поддерживать single-get (404 = нет эндпоинта) —
        # ищем пост в списке; ошибки списка не глотаем (иначе ложный «missing»)
        for p in self.list_scheduled():
            if p.id == post_id:
                return p
        return None

    def list_scheduled(self, platform: str | None = None) -> list[PostizPost]:
        # API: GET /public/v1/posts?startDate=&endDate=  ->  {"posts":[...]}
        from datetime import timedelta
        now = datetime.now(UTC)
        params = {
            "startDate": (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDate": (now + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        r = self._client.get(self.path_posts, params=params)
        r.raise_for_status()
        payload = r.json()
        items = payload if isinstance(payload, list) else (
            payload.get("posts") or payload.get("items") or payload.get("data") or []
        )
        result = []
        for data in items:
            integration = data.get("integration") or {}
            sched = _first(data, "publishDate", "scheduledFor", "scheduled_for", "date")
            st = _first(data, "state", "status", default="scheduled")
            if st and str(st).lower() not in (
                "scheduled", "queue", "pending", "draft", "published"
            ):
                continue
            content = _first(data, "content", "message", "description")
            result.append(PostizPost(
                id=str(_first(data, "id", "postId")),
                platform=_first(
                    integration, "providerIdentifier", "name",
                    default=platform or "",
                ),
                scheduled_for=datetime.fromisoformat(sched.replace("Z", "+00:00")) if sched else None,
                status=str(st).lower(),
                release_url=_first(data, "releaseURL", "releaseUrl", "release_url", "url", "releaseId"),
                content=({"text": content} if content else None),
            ))
        if platform:
            result = [p for p in result if p.platform == platform]
        return result

    def orphan_media_ids(self) -> list[str]:
        return list(self._orphan_media)

    def clear_orphan_media(self) -> list[str]:
        out = list(self._orphan_media)
        self._orphan_media.clear()
        return out
