"""TikTok Content Posting API client — dry-run / inbox v1 skeleton."""

from __future__ import annotations

from typing import Any

from ...http_client import ModuleHttpClient, mask_secrets
from ..base import ModuleError, ModuleErrorCode
from ..errors import message_for

API = "https://open.tiktokapis.com/v2"


def _map(status: int, body: str) -> ModuleError:
    t = (body or "").lower()
    d = mask_secrets((body or "")[:300])
    if status in (401, 403) or "access_token" in t:
        m, a = message_for(ModuleErrorCode.AUTH_REQUIRED, d)
        return ModuleError(ModuleErrorCode.AUTH_REQUIRED, m, action=a)
    if status == 429:
        m, a = message_for(ModuleErrorCode.RATE_LIMIT, d)
        return ModuleError(ModuleErrorCode.RATE_LIMIT, m, action=a, retryable=True)
    m, a = message_for(ModuleErrorCode.PLATFORM_REJECTED, d)
    return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, m, action=a)


class TikTokApi:
    def __init__(self, access_token: str, *, http: ModuleHttpClient | None = None, dry_run: bool = False):
        self.token = (access_token or "").strip()
        self.dry_run = dry_run
        self._http = http or ModuleHttpClient(platform="tiktok", module_version="0.2.0")
        self._n = 0

    def creator_info(self) -> dict[str, Any]:
        if self.dry_run:
            return {"creator_username": "dry_tt", "privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"]}
        # GET /post/publish/creator_info/query/
        resp = self._http.request(
            "POST",
            f"{API}/post/publish/creator_info/query/",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            json={},
        )
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        data = resp.json() if resp.content else {}
        return (data.get("data") or data) if isinstance(data, dict) else {}

    def init_upload(self, size: int, title: str = "") -> dict[str, Any]:
        if self.dry_run:
            self._n += 1
            return {"publish_id": f"tt-dry-{self._n}", "upload_url": "https://example.invalid/upload"}
        raise ModuleError(
            ModuleErrorCode.AUTH_REQUIRED,
            "TikTok live upload требует одобренного приложения / inbox",
            action="[ВЛАДЕЛЕЦ] audit package + Login Kit",
        )
