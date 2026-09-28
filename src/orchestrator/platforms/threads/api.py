"""Threads API client — dry-run; needs public media URL (B2)."""

from __future__ import annotations

from ...http_client import ModuleHttpClient, mask_secrets
from ..base import ModuleError, ModuleErrorCode
from ..errors import message_for

GRAPH = "https://graph.threads.net/v1.0"


def _map(status: int, body: str) -> ModuleError:
    d = mask_secrets((body or "")[:300])
    if status in (401, 403):
        m, a = message_for(ModuleErrorCode.AUTH_REQUIRED, d)
        return ModuleError(ModuleErrorCode.AUTH_REQUIRED, m, action=a)
    m, a = message_for(ModuleErrorCode.PLATFORM_REJECTED, d)
    return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, m, action=a)


class ThreadsApi:
    def __init__(self, access_token: str, user_id: str, *, http: ModuleHttpClient | None = None, dry_run: bool = False):
        self.token = (access_token or "").strip()
        self.user_id = (user_id or "").strip()
        self.dry_run = dry_run
        self._http = http or ModuleHttpClient(platform="threads", module_version="0.2.0")
        self._n = 0

    def create_container(self, text: str = "", video_url: str = "", image_url: str = "") -> str:
        if self.dry_run:
            self._n += 1
            return f"th-c-{self._n}"
        raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Threads live: нужен token + B2", action="[ВЛАДЕЛЕЦ]")

    def publish(self, creation_id: str) -> str:
        if self.dry_run:
            return f"th-p-{creation_id}"
        raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Threads live недоступен", action="[ВЛАДЕЛЕЦ]")
