"""Threads Graph API client (container → publish → status), injectable HTTP."""
from __future__ import annotations

import os
from typing import Any

from ...http_client import ModuleHttpClient, mask_secrets
from ..base import ModuleError, ModuleErrorCode
from ..errors import message_for


def graph_base(version: str | None = None) -> str:
    ver = (version or os.getenv("THREADS_API_VERSION") or "v1.0").strip()
    if not ver.startswith("v"):
        ver = f"v{ver}"
    return f"https://graph.threads.net/{ver}"


def _map(status: int, body: str) -> ModuleError:
    d = mask_secrets((body or "")[:300])
    if status in (401, 403):
        m, a = message_for(ModuleErrorCode.AUTH_REQUIRED, d)
        return ModuleError(ModuleErrorCode.AUTH_REQUIRED, m, action=a)
    if status == 429:
        m, a = message_for(ModuleErrorCode.RATE_LIMIT, d)
        return ModuleError(ModuleErrorCode.RATE_LIMIT, m, action=a, retryable=True)
    if status >= 500:
        m, a = message_for(ModuleErrorCode.TRANSIENT, d)
        return ModuleError(ModuleErrorCode.TRANSIENT, m, action=a, retryable=True)
    m, a = message_for(ModuleErrorCode.PLATFORM_REJECTED, d)
    return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, m, action=a)


class ThreadsApi:
    def __init__(self, access_token: str, user_id: str, *, http: ModuleHttpClient | None = None, dry_run: bool = False, api_version: str | None = None):
        self.token = (access_token or "").strip()
        self.user_id = (user_id or "").strip()
        self.dry_run = dry_run
        self._base = graph_base(api_version)
        self._http = http or ModuleHttpClient(platform="threads", module_version="0.4.0")
        self._n = 0

    def _post(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.dry_run:
            self._n += 1
            return {"id": f"th-dry-{self._n}"}
        payload = dict(params)
        payload["access_token"] = self.token
        resp = self._http.request("POST", f"{self._base}/{path.lstrip('/')}", data=payload)
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {}
        if resp.status_code >= 400 or (isinstance(body, dict) and body.get("error")):
            err = body.get("error") if isinstance(body, dict) else {}
            raise _map(resp.status_code, str((err or {}).get("message") or body or resp.text))
        return body if isinstance(body, dict) else {}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.dry_run:
            return {"id": path.split("/")[-1], "status": "FINISHED"}
        p = dict(params or {})
        p["access_token"] = self.token
        resp = self._http.request("GET", f"{self._base}/{path.lstrip('/')}", params=p)
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {}
        if resp.status_code >= 400 or (isinstance(body, dict) and body.get("error")):
            err = body.get("error") if isinstance(body, dict) else {}
            raise _map(resp.status_code, str((err or {}).get("message") or body or resp.text))
        return body if isinstance(body, dict) else {}

    def me(self) -> dict[str, Any]:
        return self._get("me", {"fields": "id,username,name"})

    def create_container(self, text: str = "", video_url: str = "", image_url: str = "") -> str:
        params: dict[str, Any] = {}
        if text:
            params["text"] = text[:500]
        if video_url:
            params.update({"media_type": "VIDEO", "video_url": video_url})
        elif image_url:
            params.update({"media_type": "IMAGE", "image_url": image_url})
        else:
            params["media_type"] = "TEXT"
        res = self._post(f"{self.user_id}/threads", params)
        cid = str(res.get("id") or "")
        if not cid:
            raise ModuleError(ModuleErrorCode.FATAL, "Threads не вернул creation/container id", action="логи")
        return cid

    def container_status(self, creation_id: str) -> dict[str, Any]:
        return self._get(creation_id, {"fields": "id,status,error_message"})

    def publish(self, creation_id: str) -> str:
        res = self._post(f"{self.user_id}/threads_publish", {"creation_id": creation_id})
        pid = str(res.get("id") or "")
        if not pid:
            raise ModuleError(ModuleErrorCode.FATAL, "Threads publish не вернул post id", action="логи")
        return pid

    def delete(self, external_id: str) -> bool:
        if self.dry_run:
            return True
        resp = self._http.request("DELETE", f"{self._base}/{external_id}", params={"access_token":self.token}, idempotent=True)
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        return True

    def publishing_limit(self) -> dict[str, Any]:
        return self._get(f"{self.user_id}/threads_publishing_limit", {"fields":"quota_usage,quota_config"})

    def get(self, external_id: str) -> dict[str, Any]:
        return self._get(external_id, {"fields": "id,text,permalink,username,timestamp"})

    def list_threads(self, limit: int = 25) -> list[dict[str, Any]]:
        body = self._get("me/threads", {"fields": "id,text,permalink,timestamp", "limit": str(limit)})
        return list(body.get("data") or [])
