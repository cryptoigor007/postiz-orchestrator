from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class MediaRef:
    """Postiz media reference: Postiz needs both the media id and its path."""
    id: str
    path: str


@dataclass
class PostizPost:
    id: str
    platform: str
    scheduled_for: datetime | None
    status: str
    release_url: str | None = None
    content: dict[str, Any] | None = None
    # Человекочитаемая причина, если Postiz её вернул (в этой сборке текст ошибки
    # приходит не в посте, а в /public/v1/notifications — см. postiz_errors).
    error: str | None = None


class PostizClient(Protocol):
    def upload_media(self, path: str, platform: str) -> MediaRef:
        """Upload media, return its id + path."""
        ...

    def create_post(self, platform: str, media: MediaRef | str | None,
                    content: dict[str, Any],
                    scheduled_for: datetime | None = None) -> PostizPost:
        ...

    def delete_post(self, post_id: str) -> None:
        ...

    def get_post(self, post_id: str) -> PostizPost | None:
        ...

    def list_scheduled(self, platform: str | None = None) -> list[PostizPost]:
        ...

    def list_error_notifications(self) -> list[dict[str, Any]]:
        """Уведомления Postiz об ошибках публикации: [{platform, reason, created_at}]."""
        ...


class PostizRouter:
    """Маршрутизация по id: `tg:<id>` — пост нашего бота, остальное — Postiz.

    Панель, синхронизация статусов и удаление ходят в один объект-клиент, поэтому
    достаточно обернуть им HttpPostizClient/MockPostizClient при сборке в main.py.
    """

    def __init__(self, postiz: Any, telegram: Any = None):
        self.postiz = postiz
        self.telegram = telegram

    def __getattr__(self, name: str) -> Any:
        # всё, что не переопределено ниже, прозрачно уходит в Postiz
        return getattr(self.postiz, name)

    def handles(self, post_id: Any) -> bool:
        from .telegram_publish import is_bot_post_id

        return is_bot_post_id(post_id) and self.telegram is not None

    def delete_post(self, post_id: str) -> None:
        if self.handles(post_id):
            return self.telegram.delete_post(str(post_id))
        return self.postiz.delete_post(post_id)

    def get_post(self, post_id: str) -> PostizPost | None:
        if self.handles(post_id):
            return None  # у Bot API нет «получить пост»: состояние знаем из своей БД
        return self.postiz.get_post(post_id)

    def set_status(self, post_id: str, status: str) -> None:
        if self.handles(post_id):
            return None
        fn = getattr(self.postiz, "set_status", None)
        return fn(post_id, status) if fn else None

    def mark_published(self, post_id: str, release_url: str | None = None) -> None:
        if self.handles(post_id):
            return None
        fn = getattr(self.postiz, "mark_published", None)
        return fn(post_id, release_url) if fn else None


class MockPostizClient:
    """In-memory mock for tests and dry-run."""

    def __init__(self):
        self.media: dict[str, str] = {}
        self.posts: dict[str, PostizPost] = {}
        self._counter = 0
        self.fail_create = False
        self.fail_upload = False
        self._orphan_media: list[str] = []
        # уведомления об ошибках (аналог /public/v1/notifications в Postiz)
        self.notifications: list[dict[str, Any]] = []

    def upload_media(self, path: str, platform: str) -> MediaRef:
        if self.fail_upload:
            raise RuntimeError("upload_failed")
        mid = hashlib.md5(f"{path}:{platform}".encode()).hexdigest()[:12]
        self.media[mid] = path
        return MediaRef(id=mid, path=path)

    def create_post(self, platform: str, media: MediaRef | str | None,
                    content: dict[str, Any],
                    scheduled_for: datetime | None = None) -> PostizPost:
        media_id = media.id if isinstance(media, MediaRef) else (str(media) if media else "")
        if self.fail_create:
            self._orphan_media.append(media_id)
            raise RuntimeError("create_failed")
        self._counter += 1
        pid = f"post_{self._counter}"
        post = PostizPost(
            id=pid,
            platform=platform,
            scheduled_for=scheduled_for,
            status="scheduled" if scheduled_for else "published",
            content=content,
        )
        self.posts[pid] = post
        return post

    def delete_post(self, post_id: str) -> None:
        self.posts.pop(post_id, None)

    def set_status(self, post_id: str, status: str) -> None:
        post = self.posts.get(post_id)
        if post:
            self.posts[post_id] = PostizPost(
                id=post.id, platform=post.platform, scheduled_for=post.scheduled_for,
                status=status, release_url=post.release_url, content=post.content,
                error=post.error,
            )

    def set_error(self, post_id: str, error: str) -> None:
        """Тесты/отладка: Postiz пометил пост ошибкой с таким текстом."""
        post = self.posts.get(post_id)
        if post:
            self.posts[post_id] = PostizPost(
                id=post.id, platform=post.platform, scheduled_for=post.scheduled_for,
                status="error", release_url=post.release_url, content=post.content,
                error=error,
            )

    def add_error_notification(self, content: str, created_at: str,
                               platform: str | None = None) -> dict[str, Any]:
        """Тесты: положить уведомление об ошибке (как отдаёт Postiz)."""
        from .postiz_errors import parse_error_notification

        parsed = parse_error_notification(content)
        if parsed is None:
            raise ValueError("не похоже на уведомление об ошибке")
        plat, reason = parsed
        item = {"platform": platform or plat, "reason": reason, "created_at": created_at}
        self.notifications.append(item)
        return item

    def list_error_notifications(self) -> list[dict[str, Any]]:
        return list(self.notifications)

    def get_post(self, post_id: str) -> PostizPost | None:
        return self.posts.get(post_id)

    def list_scheduled(self, platform: str | None = None) -> list[PostizPost]:
        res = [p for p in self.posts.values() if p.status == "scheduled"]
        if platform:
            res = [p for p in res if p.platform == platform]
        return res

    def mark_published(self, post_id: str, release_url: str | None = None) -> None:
        p = self.posts.get(post_id)
        if p:
            p.status = "published"
            if release_url:
                p.release_url = release_url

    def orphan_media_ids(self) -> list[str]:
        return list(self._orphan_media)

    def clear_orphan_media(self) -> list[str]:
        out = list(self._orphan_media)
        self._orphan_media.clear()
        return out
