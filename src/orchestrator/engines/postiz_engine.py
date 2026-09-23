from __future__ import annotations

from typing import Any

from ..postiz import PostizClient
from .base import PublishResult
from .registry import capabilities


class PostizEngine:
    """Adapter: existing Postiz client behind the Destination interface."""

    engine = "postiz"

    def __init__(self, client: PostizClient):
        self.client = client

    def capabilities(self) -> dict[str, bool]:
        return capabilities("postiz")

    def publish(self, platform: str, media_path: str, content: dict[str, Any],
                scheduled_for: Any = None) -> PublishResult:
        media = self.client.upload_media(media_path, platform)
        post = self.client.create_post(
            platform=platform, media=media, content=content, scheduled_for=scheduled_for
        )
        return PublishResult(
            engine=self.engine,
            platform=platform,
            external_id=post.id,
            url=post.release_url,
            state=post.status,
        )

    def list_uploads(self, params: dict | None = None) -> list[dict]:
        # Postiz cannot list arbitrary channel uploads; not supported.
        raise NotImplementedError("postiz engine does not support list_uploads")

    def update_metadata(self, external_id: str, data: dict) -> bool:
        return False

    def delete(self, external_id: str) -> bool:
        self.client.delete_post(external_id)
        return True

    def check_claims(self, external_id: str) -> dict:
        return {"status": "unknown"}
