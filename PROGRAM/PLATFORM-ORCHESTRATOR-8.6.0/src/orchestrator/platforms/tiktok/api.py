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

    def init_upload(self, size: int, title: str = "", *, privacy_level: str = "PUBLIC_TO_EVERYONE", description: str = "", chunk_size: int | None = None, total_chunk_count: int | None = None) -> dict[str, Any]:
        if self.dry_run:
            self._n += 1
            return {"publish_id": f"tt-dry-{self._n}", "upload_url": "https://example.invalid/upload"}
        if int(size) <= 0: raise ModuleError(ModuleErrorCode.MEDIA_INVALID,"TikTok: media size must be positive")
        body={"post_info":{"title":str(title)[:150],"privacy_level":privacy_level,"disable_duet":False,"disable_comment":False,"disable_stitch":False},"source_info":{"source":"FILE_UPLOAD","video_size":int(size)}}
        if description: body["post_info"]["description"]=str(description)[:2200]
        if chunk_size is not None:
            body["source_info"]["chunk_size"] = int(chunk_size)
        if total_chunk_count is not None:
            body["source_info"]["total_chunk_count"] = int(total_chunk_count)
        resp=self._http.request("POST",f"{API}/post/publish/video/init/",headers={"Authorization":f"Bearer {self.token}","Content-Type":"application/json"},json=body,idempotent=False)
        if resp.status_code>=400: raise _map(resp.status_code,resp.text)
        data=resp.json() if resp.content else {}
        out=data.get("data") or data
        if not out.get("publish_id") or not out.get("upload_url"): raise ModuleError(ModuleErrorCode.FATAL,"TikTok: init response missing publish_id/upload_url")
        return out

    def upload_file(self, upload_url: str, path: str, *, chunk_size: int | None = None) -> bool:
        from pathlib import Path
        p=Path(path)
        if not p.is_file(): raise ModuleError(ModuleErrorCode.MEDIA_INVALID,f"TikTok: file not found: {path}")
        size=p.stat().st_size
        if size <= 0: raise ModuleError(ModuleErrorCode.MEDIA_INVALID,"TikTok: empty video file")
        if chunk_size is None:
            # TikTok allows 5 MB..64 MB chunks; files below 5 MB are one chunk.
            chunk_size = size if size < 5 * 1024 * 1024 else 10 * 1024 * 1024
        chunk_size = max(5 * 1024 * 1024, min(int(chunk_size), 64 * 1024 * 1024)) if size >= 5 * 1024 * 1024 else size
        offset=0
        with p.open("rb") as fh:
            while offset < size:
                data=fh.read(min(chunk_size, size-offset))
                if not data: break
                end=offset + len(data) - 1
                resp=self._http.request(
                    "PUT", upload_url,
                    headers={"Content-Range":f"bytes {offset}-{end}/{size}","Content-Type":"video/mp4","Content-Length":str(len(data))},
                    content=data, upload=True, idempotent=True,
                )
                if resp.status_code>=400: raise _map(resp.status_code,resp.text)
                if resp.status_code not in (200,201,204,206):
                    raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED,f"TikTok: unexpected upload response {resp.status_code}")
                offset=end+1
        return offset == size

    def fetch_status(self, publish_id: str) -> dict[str,Any]:
        if self.dry_run: return {"status":"PUBLISH_COMPLETE","publish_id":publish_id}
        resp=self._http.request("POST",f"{API}/post/publish/status/fetch/",headers={"Authorization":f"Bearer {self.token}","Content-Type":"application/json"},json={"publish_id":publish_id},idempotent=True)
        if resp.status_code>=400: raise _map(resp.status_code,resp.text)
        data=resp.json() if resp.content else {}
        return data.get("data") or data
