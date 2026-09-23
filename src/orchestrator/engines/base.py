from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class PublishResult:
    engine: str
    platform: str
    external_id: str
    url: str | None
    state: str


@runtime_checkable
class Destination(Protocol):
    """Universal publication destination (Postiz, direct API, n8n, browser)."""

    engine: str

    def capabilities(self) -> dict[str, bool]: ...

    def publish(self, platform: str, media_path: str, content: dict[str, Any],
                scheduled_for: Any = None) -> PublishResult: ...

    def list_uploads(self, params: dict | None = None) -> list[dict]: ...

    def update_metadata(self, external_id: str, data: dict) -> bool: ...

    def delete(self, external_id: str) -> bool: ...

    def check_claims(self, external_id: str) -> dict: ...
