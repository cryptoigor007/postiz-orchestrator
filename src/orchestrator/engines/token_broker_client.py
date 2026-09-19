from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any


def _urllib_http(method: str, url: str, params: dict, headers: dict,
                 body: dict | None = None) -> dict:
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers = {**headers, "Content-Type": "application/json"}
    else:
        if params:
            url += "?" + urllib.parse.urlencode(params)
        params = {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            msg = json.loads(raw).get("error", raw)
        except Exception:
            msg = raw
        raise RuntimeError(f"token broker: {msg}") from e


class TokenBrokerClient:
    """Fetches a platform OAuth token from the on-server token broker."""

    def __init__(self, url: str, secret: str,
                 http: Callable[[str, str, dict, dict], dict] | None = None):
        self.url = url.rstrip("/")
        self.secret = secret
        self._http = http or _urllib_http

    def symlink(self, src: str) -> dict[str, Any]:
        """Создать симлинк в хранилище Postiz на файл сервера (без копии)."""
        return self._http("POST", self.url + "/symlink", {},
                          {"X-Broker-Secret": self.secret}, {"src": src})

    def get(self, platform: str, integration_id: str | None = None) -> dict[str, Any]:
        params = {"platform": platform}
        if integration_id:
            params["id"] = integration_id
        return self._http("GET", self.url + "/token", params,
                          {"X-Broker-Secret": self.secret})
