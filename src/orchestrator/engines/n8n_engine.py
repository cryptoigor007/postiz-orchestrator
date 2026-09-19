from __future__ import annotations
import json
import urllib.parse
import urllib.request
from typing import Any, Callable

from .base import PublishResult
from .registry import capabilities


def _urllib_http(method: str, url: str, params: dict | None, json_body: dict | None,
                 headers: dict) -> dict:
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(json_body).encode() if json_body is not None else None
    h = dict(headers)
    if data:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=40) as r:
        body = r.read().decode()
        return json.loads(body) if body else {}


class N8nEngine:
    """Publication via n8n workflows (webhooks)."""

    engine = "n8n"

    def __init__(self, base_url: str, token: str = "",
                 http: Callable[..., dict] | None = None):
        self.base = base_url.rstrip("/")
        self.token = token
        self._http = http or _urllib_http

    def capabilities(self) -> dict[str, bool]:
        return capabilities("n8n")

    def _h(self) -> dict:
        return {"X-N8N-Token": self.token} if self.token else {}

    def publish(self, platform: str, media_path: str, content: dict[str, Any],
                scheduled_for: Any = None) -> PublishResult:
        res = self._http("POST", f"{self.base}/webhook/postiz-publish", None, {
            "platform": platform, "media_path": media_path, "content": content,
            "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
        }, self._h())
        return PublishResult(engine=self.engine, platform=platform,
                             external_id=str(res.get("id", "")),
                             url=res.get("url"), state=res.get("state", "scheduled"))

    def list_uploads(self, params: dict | None = None) -> list[dict]:
        res = self._http("GET", f"{self.base}/webhook/postiz-uploads", params or {}, None, self._h())
        return res.get("items", [])

    def update_metadata(self, external_id: str, data: dict) -> bool:
        return False

    def delete(self, external_id: str) -> bool:
        return False

    def check_claims(self, external_id: str) -> dict:
        return {"status": "unknown"}
