from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from .postiz import MediaRef, PostizPost
from .postiz_errors import parse_error_notification, short_reason

logger = logging.getLogger(__name__)


def is_safe_retry(e: Exception) -> bool:
    """Безопасно ли повторить запрос: точно ли он НЕ был обработан сервером.

    Создание поста повтором на таймауте могло бы дать ДУБЛИКАТ, поэтому для POST
    повторяем только когда соединение не состоялось (или 429 — лимит, пост не создан).
    """
    if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)):
        return True
    if isinstance(e, httpx.HTTPStatusError):
        code = getattr(getattr(e, "response", None), "status_code", 0)
        return code == 429
    return False


def _retry_after_seconds(r) -> float | None:
    """Retry-After из ответа (сек), clamp 1..60; None если нет/невалиден."""
    try:
        raw = (r.headers.get("retry-after") or "").strip()
    except Exception:
        return None
    if not raw:
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    return max(1.0, min(60.0, val))


def _request_with_retry(client: httpx.Client, method: str, url: str, retries: int = 3, **kwargs):
    is_post = method.upper() == "POST"
    last = None
    for i in range(retries):
        try:
            r = client.request(method, url, **kwargs)
            if r.status_code == 429:
                # лимит: пост/ресурс НЕ создан — повторять безопасно
                sleep_for = _retry_after_seconds(r)
                last = httpx.HTTPStatusError("rate limited", request=r.request, response=r)
                import time
                time.sleep(sleep_for if sleep_for is not None else 1.5 * (i + 1))
                continue
            if r.status_code >= 500 and not is_post:
                raise httpx.HTTPStatusError("server error", request=r.request, response=r)
            return r  # для POST 5xx отдаём вызывающему (повтор мог бы создать дубликат)
        except Exception as e:
            last = e
            if is_post and not is_safe_retry(e):
                raise  # повтор на таймауте/ошибке сервера рискован для POST
            import time
            time.sleep(1.5 * (i + 1))
    if last is not None:
        raise last
    raise RuntimeError("retry loop exhausted")


def _first(data: dict, *keys: str, default=None):
    for k in keys:
        if k in data and data[k] is not None:
            return data[k]
    return default


def _upload_path(data: dict) -> str | None:
    return _first(data, "path", "url")


def _release_url(data: dict, platform: str = "") -> str | None:
    """Ссылка на опубликованный пост.

    `releaseURL` — готовая ссылка; у YouTube в `releaseId` лежит id видео
    (KFaFvDX7H4k), поэтому собираем ссылку сами. Чужой внутренний id за ссылку
    не выдаём: иначе в панели и в Telegram появится «ссылка», которая никуда не ведёт.
    """
    url = _first(data, "releaseURL", "releaseUrl", "release_url", "url")
    if url:
        return str(url)
    rid = _first(data, "releaseId", "release_id")
    if not rid:
        return None
    rid = str(rid).strip()
    if not rid:
        return None
    if rid.startswith("http://") or rid.startswith("https://"):
        return rid
    if platform == "youtube":
        return f"https://www.youtube.com/watch?v={rid}"
    return None


def _error_text(data: dict) -> str | None:
    """Человекочитаемая причина ошибки из ответа, если Postiz её там отдал."""
    raw = _first(data, "error", "errors", "failureReason", "failure_reason", "reason")
    if raw is None:
        return None
    for _ in range(4):
        if isinstance(raw, dict):
            raw = (raw.get("message") or raw.get("failure") or raw.get("cause")
                   or raw.get("error") or raw)
        elif isinstance(raw, list) and raw:
            raw = raw[0]
        else:
            break
    text = short_reason(raw, 500)
    return text or None


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
        self.path_notifications = os.getenv("POSTIZ_PATH_NOTIFICATIONS",
                                            "/public/v1/notifications")
        if verify is None:
            # A8: TLS verify ON by default. POSTIZ_VERIFY_TLS умеет:
            #   "1/true/yes/on"  → проверка с системными CA
            #   "/path/ca.pem"   → проверка с ЗАДАННЫМ CA (правильный путь для self-signed)
            #   "0/false/no/off" → отключено (только локальная отладка, в бою запрещено)
            insecure = os.getenv("POSTIZ_INSECURE_TLS", "").strip().lower() in (
                "1", "true", "yes", "on",
            )
            explicit = os.getenv("POSTIZ_VERIFY_TLS", "").strip()
            low = explicit.lower()
            if low in ("0", "false", "no", "off"):
                verify = False
            elif low in ("1", "true", "yes", "on"):
                verify = True
            elif explicit and os.path.isfile(explicit):
                # A8: pinned CA. Для self-signed leaf, который сам себе CA, OpenSSL требует
                # VERIFY_X509_PARTIAL_CHAIN — иначе «self-signed certificate».
                import ssl as _ssl

                ctx = _ssl.create_default_context(cafile=explicit)
                try:
                    ctx.verify_flags |= _ssl.VERIFY_X509_PARTIAL_CHAIN
                except AttributeError:  # старый Python
                    logger.warning("VERIFY_X509_PARTIAL_CHAIN недоступен — pinned CA может не сработать")
                verify = ctx  # httpx принимает SSLContext
            elif explicit:
                logger.warning("POSTIZ_VERIFY_TLS=%r не файл и не bool — использую системные CA", explicit)
                verify = not insecure
            else:
                verify = not insecure  # default secure
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
            release_url=_release_url(data, str(platform or "")),
            content=content,
        )

    def delete_post(self, post_id: str) -> None:
        # DELETE идемпотентен → retry-helper (429/5xx/таймауты безопасны)
        r = _request_with_retry(self._client, "DELETE", f"{self.path_posts}/{post_id}",
                                timeout=10.0)
        if r.status_code not in (200, 204, 404):
            r.raise_for_status()

    def set_status(self, post_id: str, status: str) -> None:
        r = _request_with_retry(self._client, "PUT", f"{self.path_posts}/{post_id}/status",
                                json={"status": status}, timeout=15.0)
        if r.status_code not in (200, 204):
            r.raise_for_status()

    def set_release_id(self, post_id: str, release_id: str) -> None:
        r = _request_with_retry(
            self._client, "PUT", f"{self.path_posts}/{post_id}/release-id",
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
            platform = str(_first(integration, "providerIdentifier", "name",
                                 "platform", default=""))
            sched = _first(data, "publishDate", "scheduledFor", "scheduled_for", "date")
            status = _first(data, "state", "status", default="unknown")
            return PostizPost(
                id=str(_first(data, "id", "postId") or post_id),
                platform=platform,
                scheduled_for=datetime.fromisoformat(sched.replace("Z", "+00:00")) if sched else None,
                status=str(status).lower(),
                release_url=_release_url(data, platform),
                content=({"text": data["content"]} if data.get("content") else None),
                error=_error_text(data),
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
        r = _request_with_retry(self._client, "GET", self.path_posts, params=params)
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
                "scheduled", "queue", "pending", "draft", "published", "error"
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
                release_url=_release_url(data, str(platform or "")),
                content=({"text": content} if content else None),
                error=_error_text(data),
            ))
        if platform:
            result = [p for p in result if p.platform == platform]
        return result

    def list_error_notifications(self) -> list[dict[str, Any]]:
        """Ошибки публикации из уведомлений Postiz: [{platform, reason, created_at}].

        `GET /public/v1/posts` отдаёт только state=ERROR без причины, а текст ошибки
        лежит в /public/v1/notifications («An error occurred while posting on …»).
        """
        r = _request_with_retry(self._client, "GET", self.path_notifications, timeout=20.0)
        r.raise_for_status()
        payload = r.json()
        items = payload if isinstance(payload, list) else (
            payload.get("notifications") or payload.get("items") or payload.get("data") or []
        )
        out: list[dict[str, Any]] = []
        for n in items:
            if not isinstance(n, dict):
                continue
            parsed = parse_error_notification(_first(n, "content", "message", "text"))
            if parsed is None:
                continue
            platform, reason = parsed
            out.append({
                "platform": platform or "",
                "reason": reason,
                "created_at": str(_first(n, "createdAt", "created_at", "date", default="") or ""),
            })
        return out

    def orphan_media_ids(self) -> list[str]:
        return list(self._orphan_media)

    def clear_orphan_media(self) -> list[str]:
        out = list(self._orphan_media)
        self._orphan_media.clear()
        return out
