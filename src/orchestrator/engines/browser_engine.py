from __future__ import annotations
from typing import Any

from .base import PublishResult
from .registry import capabilities


class BrowserEngine:
    """Experimental browser-automation destination (Playwright). Last resort
    for platforms without an API. Not implemented until a concrete platform
    requires it (see spec Phase 4)."""

    engine = "browser"

    def __init__(self, profile_dir: str | None = None, headless: bool = True):
        self.profile_dir = profile_dir
        self.headless = headless

    def available(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except Exception:
            return False

    def capabilities(self) -> dict[str, bool]:
        return capabilities("browser")

    def _unsupported(self):
        raise NotImplementedError(
            "browser engine is experimental and not enabled for this platform"
        )

    def publish(self, platform: str, media_path: str, content: dict[str, Any],
                scheduled_for: Any = None) -> PublishResult:
        self._unsupported()

    def list_uploads(self, params: dict | None = None) -> list[dict]:
        self._unsupported()

    def update_metadata(self, external_id: str, data: dict) -> bool:
        self._unsupported()

    def delete(self, external_id: str) -> bool:
        self._unsupported()

    def check_claims(self, external_id: str) -> dict:
        return {"status": "unknown"}
