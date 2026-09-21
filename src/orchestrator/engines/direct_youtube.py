from __future__ import annotations

import json as _json
import re
import ssl
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from .registry import capabilities

API = "https://www.googleapis.com/youtube/v3"
_ISO = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def iso_duration_seconds(value: str | None) -> float | None:
    if not value:
        return None
    m = _ISO.fullmatch(value)
    if not m:
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return float(d * 86400 + h * 3600 + mi * 60 + s)


class UrllibHttp:
    """Default transport: Bearer token, optional TLS-verify off."""

    def __init__(self, verify: bool = True):
        self.ctx = ssl.create_default_context()
        if not verify:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def request(self, method: str, url: str, params: dict | None = None,
                json: dict | None = None, token: str = "") -> dict:
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = _json.dumps(json).encode() if json is not None else None
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if data:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=40, context=self.ctx) as r:
            body = r.read().decode()
            return _json.loads(body) if body else {}


class YouTubeEngine:
    engine = "direct"

    def __init__(self, token_provider: Callable[[], str], http: Any | None = None):
        self._token_provider = token_provider
        self.http = http or UrllibHttp()

    def capabilities(self) -> dict[str, bool]:
        return capabilities("direct")

    def _req(self, method: str, path: str, params=None, json=None) -> dict:
        return self.http.request(method, API + path, params, json, self._token_provider())

    def list_uploads(self, params: dict | None = None) -> list[dict]:
        max_results = int((params or {}).get("max_results", 50))
        ch = self._req("GET", "/channels", {"part": "contentDetails", "mine": "true"})
        items = ch.get("items") or []
        if not items:
            return []
        uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        pl = self._req("GET", "/playlistItems", {
            "part": "snippet,contentDetails", "playlistId": uploads,
            "maxResults": max_results,
        })
        vids = []
        base = []
        for it in pl.get("items") or []:
            vid = (it.get("contentDetails") or {}).get("videoId")
            if not vid:
                continue
            sn = it.get("snippet") or {}
            vids.append(vid)
            base.append({
                "external_id": vid,
                "title": sn.get("title"),
                "description": sn.get("description"),
                "published_at": sn.get("publishedAt"),
                "thumbnail_url": ((sn.get("thumbnails") or {}).get("high") or {}).get("url"),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "duration_sec": None,
                "privacy": None,
            })
        if vids:
            details = self._req("GET", "/videos", {
                "part": "contentDetails,status", "id": ",".join(vids),
            })
            by_id = {d.get("id"): d for d in details.get("items") or []}
            for row in base:
                d = by_id.get(row["external_id"]) or {}
                row["duration_sec"] = iso_duration_seconds(
                    (d.get("contentDetails") or {}).get("duration")
                )
                row["privacy"] = (d.get("status") or {}).get("privacyStatus")
        return base

    def update_metadata(self, external_id: str, data: dict) -> bool:
        cur = self._req("GET", "/videos", {"part": "snippet", "id": external_id})
        items = cur.get("items") or []
        if not items:
            return False
        snippet = dict(items[0].get("snippet") or {})
        if "title" in data and data["title"] is not None:
            snippet["title"] = data["title"]
        if "description" in data and data["description"] is not None:
            snippet["description"] = data["description"]
        body = {"id": external_id, "snippet": snippet}
        res = self._req("PUT", "/videos", {"part": "snippet"}, json=body)
        return bool(res.get("items"))

    def delete(self, external_id: str) -> bool:
        """P1.9: True возвращается ТОЛЬКО при успешном DELETE; ошибка HTTP — исключение."""
        self._req("DELETE", "/videos", {"id": external_id})
        return True

    def check_claims(self, external_id: str) -> dict:
        # Content ID claims are not exposed by the public Data API.
        return {"status": "unknown",
                "note": "Content ID claims require the YouTube CMS (partner) API"}
