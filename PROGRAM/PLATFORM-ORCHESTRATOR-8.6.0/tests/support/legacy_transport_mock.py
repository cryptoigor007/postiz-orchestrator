"""Test-only mock for legacy transport API (DEPRECATED — not used in production)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class PostizPost:
    id: str
    platform: str = ""
    status: str = "scheduled"
    content: dict[str, Any] = field(default_factory=dict)
    scheduled_for: datetime | None = None
    release_url: str | None = None
    media: Any = None

class MockPostizClient:
    def __init__(self, *a, **k):
        self.posts: dict[str, PostizPost] = {}
        self.media: dict[str, Any] = {}
        self._n = 0
        self.deleted: list[str] = []
        self._orphan_media: list[Any] = []
    def create_post(self, platform, media=None, content=None, scheduled_for=None, **kw):
        self._n += 1
        pid = f"mock-{self._n}"
        post = PostizPost(id=pid, platform=platform,
            status="scheduled" if scheduled_for else "published",
            content=dict(content or {}), scheduled_for=scheduled_for, media=media)
        self.posts[pid] = post
        return post
    def delete_post(self, post_id: str) -> bool:
        self.deleted.append(post_id)
        self.posts.pop(post_id, None)
        return True
    def upload_media(self, path, platform=""):
        mid = f"media-{len(self.media)+1}"
        self.media[mid] = {"id": mid, "path": path, "platform": platform}
        return {"id": mid, "path": path}
    def get_post(self, post_id):
        return self.posts.get(post_id)
    def list_posts(self, **kw):
        return list(self.posts.values())

    def set_status(self, post_id, status):
        p = self.posts.get(post_id)
        if p: p.status = status
        return bool(p)

    def mark_published(self, post_id, url=""):
        p = self.posts.get(post_id)
        if not p: return False
        p.status = "published"
        if url: p.release_url = url
        return True
    def mark_published(self, post_id: str, url: str = "") -> bool:
        p = self.posts.get(post_id)
        if not p: return False
        p.status = "published"
        if url: p.release_url = url
        return True
    def update_post(self, post_id: str, **kw) -> bool:
        p = self.posts.get(post_id)
        if not p: return False
        for k, v in kw.items():
            if hasattr(p, k): setattr(p, k, v)
        return True

class PostizRouter:
    def __init__(self, client=None, *args, **kw):
        self.client = client if client is not None and hasattr(client, 'create_post') else MockPostizClient()
        if args and hasattr(args[0], 'create_post'): self.client = args[0]
    def __getattr__(self, name):
        return getattr(self.client, name)

HttpPostizClient = MockPostizClient
