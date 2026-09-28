"""Facebook Graph Page publish client — dry-run ready."""

from __future__ import annotations

import logging
from typing import Any

from ...http_client import ModuleHttpClient, mask_secrets
from ..base import ModuleError, ModuleErrorCode
from ..errors import message_for

logger = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v25.0"


def _map(status: int, body: str) -> ModuleError:
    t = (body or "").lower()
    d = mask_secrets((body or "")[:300])
    if status in (401, 190) or "session" in t:
        m, a = message_for(ModuleErrorCode.AUTH_EXPIRED, d)
        return ModuleError(ModuleErrorCode.AUTH_EXPIRED, m, action=a)
    if status == 429:
        m, a = message_for(ModuleErrorCode.RATE_LIMIT, d)
        return ModuleError(ModuleErrorCode.RATE_LIMIT, m, action=a, retryable=True)
    if status >= 500:
        m, a = message_for(ModuleErrorCode.TRANSIENT, f"HTTP {status}")
        return ModuleError(ModuleErrorCode.TRANSIENT, m, action=a, retryable=True)
    m, a = message_for(ModuleErrorCode.PLATFORM_REJECTED, d)
    return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, m, action=a)


class FacebookApi:
    def __init__(self, page_token: str, page_id: str, *, http: ModuleHttpClient | None = None, dry_run: bool = False):
        self.token = (page_token or "").strip()
        self.page_id = (page_id or "").strip()
        self.dry_run = dry_run
        self._http = http or ModuleHttpClient(platform="facebook", module_version="0.2.0")
        self._n = 0

    def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        if self.dry_run:
            self._n += 1
            return {"id": f"fb-dry-{self._n}"}
        data = {**data, "access_token": self.token}
        resp = self._http.request("POST", f"{GRAPH}/{path.lstrip('/')}", data=data)
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {}
        if resp.status_code >= 400 or (isinstance(body, dict) and body.get("error")):
            err = (body or {}).get("error") or {}
            raise _map(resp.status_code, str(err.get("message") or body or resp.text))
        return body if isinstance(body, dict) else {}

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        if self.dry_run:
            return {"id": self.page_id, "name": "dry_page"}
        p = {**(params or {}), "access_token": self.token}
        resp = self._http.request("GET", f"{GRAPH}/{path.lstrip('/')}", params=p)
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {}
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        return body if isinstance(body, dict) else {}

    def page_info(self) -> dict[str, Any]:
        return self._get(self.page_id, {"fields": "id,name"})

    def feed_post(self, message: str, link: str = "") -> str:
        data: dict[str, Any] = {"message": message[:5000]}
        if link:
            data["link"] = link
        res = self._post(f"{self.page_id}/feed", data)
        return str(res.get("id") or "")

    def video_post(self, file_url: str, description: str = "") -> str:
        res = self._post(
            f"{self.page_id}/videos",
            {"file_url": file_url, "description": description[:5000]},
        )
        return str(res.get("id") or "")

    def delete(self, object_id: str) -> bool:
        if self.dry_run:
            return True
        resp = self._http.request(
            "DELETE",
            f"{GRAPH}/{object_id}",
            params={"access_token": self.token},
        )
        return resp.status_code < 400
