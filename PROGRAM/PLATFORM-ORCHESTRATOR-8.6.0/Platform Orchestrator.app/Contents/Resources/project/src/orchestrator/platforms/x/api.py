"""X API v2 client — dry-run + mockable."""
from __future__ import annotations

from typing import Any
from pathlib import Path

from ...http_client import ModuleHttpClient, mask_secrets
from ..base import ModuleError, ModuleErrorCode
from ..errors import message_for

API = "https://api.x.com/2"
UPLOAD = "https://upload.twitter.com/1.1"


def _map(status: int, body: str) -> ModuleError:
    t = (body or "").lower()
    d = mask_secrets((body or "")[:300])
    if status in (401, 403) or "unauthorized" in t:
        m, a = message_for(ModuleErrorCode.AUTH_REQUIRED, d)
        return ModuleError(ModuleErrorCode.AUTH_REQUIRED, m, action=a)
    if status == 429:
        m, a = message_for(ModuleErrorCode.RATE_LIMIT, d)
        return ModuleError(ModuleErrorCode.RATE_LIMIT, m, action=a, retryable=True)
    m, a = message_for(ModuleErrorCode.PLATFORM_REJECTED, d)
    return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, m, action=a)


class XApi:
    def __init__(
        self,
        access_token: str,
        *,
        http: ModuleHttpClient | None = None,
        dry_run: bool = False,
    ) -> None:
        self.token = (access_token or "").strip()
        self.dry_run = dry_run
        self._http = http or ModuleHttpClient(platform="x", module_version="0.1.0")
        self._n = 0

    def create_tweet(self, text: str, media_ids: list[str] | None = None) -> dict[str, Any]:
        if self.dry_run:
            self._n += 1
            return {"id": str(self._n), "text": text[:50]}
        body: dict[str, Any] = {"text": text}
        if media_ids:
            body["media"] = {"media_ids": media_ids}
        resp = self._http.request(
            "POST",
            f"{API}/tweets",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        data = resp.json() if resp.content else {}
        return (data.get("data") or data) if isinstance(data, dict) else {}

    def get_tweet(self, tweet_id: str) -> dict[str, Any]:
        """Read a tweet from X; live state is authoritative only after this read."""
        if self.dry_run:
            return {"id": str(tweet_id), "text": "dry-run"}
        resp = self._http.request(
            "GET",
            f"{API}/tweets/{tweet_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            params={"tweet.fields": "created_at,public_metrics"},
            idempotent=True,
        )
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        data = resp.json() if resp.content else {}
        if not isinstance(data, dict) or not data.get("data"):
            raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED, "tweet not found")
        return data["data"]

    def delete_tweet(self, tweet_id: str) -> bool:
        if self.dry_run:
            return True
        resp = self._http.request(
            "DELETE",
            f"{API}/tweets/{tweet_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        return True

    def upload_media(self, path: str, *, media_type: str = "image/jpeg", chunk_size: int = 4 * 1024 * 1024) -> str:
        """Upload image directly or video through INIT/APPEND/FINALIZE."""
        if self.dry_run:
            self._n += 1
            return f"media_{self._n}"
        p = Path(path)
        if not p.is_file():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"media not found: {path}")
        is_video = media_type.startswith("video/") or p.suffix.lower() in {".mp4", ".mov", ".m4v"}
        if not is_video:
            with open(p, "rb") as fh:
                resp = self._http.request(
                    "POST", f"{UPLOAD}/media/upload.json",
                    headers={"Authorization": f"Bearer {self.token}"},
                    files={"media": (p.name, fh)}, upload=True, idempotent=False,
                )
            if resp.status_code >= 400:
                raise _map(resp.status_code, resp.text)
            data = resp.json() if resp.content else {}
            mid = str((data or {}).get("media_id_string") or (data or {}).get("media_id") or "")
            if not mid:
                raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED, "no media_id in image upload response")
            return mid

        total = p.stat().st_size
        init = self._http.request(
            "POST", f"{UPLOAD}/media/upload.json",
            headers={"Authorization": f"Bearer {self.token}"},
            params={"command":"INIT", "total_bytes":str(total), "media_type":media_type, "media_category":"tweet_video"},
            upload=True, idempotent=False,
        )
        if init.status_code >= 400:
            raise _map(init.status_code, init.text)
        init_data = init.json() if init.content else {}
        media_id = str((init_data or {}).get("media_id_string") or (init_data or {}).get("media_id") or "")
        if not media_id:
            raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED, "X INIT did not return media_id")

        with open(p, "rb") as fh:
            segment = 0
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                resp = self._http.request(
                    "POST", f"{UPLOAD}/media/upload.json",
                    headers={"Authorization": f"Bearer {self.token}"},
                    params={"command":"APPEND", "media_id":media_id, "segment_index":str(segment)},
                    files={"media": (p.name, chunk)}, upload=True, idempotent=False,
                )
                if resp.status_code >= 400:
                    raise _map(resp.status_code, resp.text)
                segment += 1

        final = self._http.request(
            "POST", f"{UPLOAD}/media/upload.json",
            headers={"Authorization": f"Bearer {self.token}"},
            params={"command":"FINALIZE", "media_id":media_id}, upload=True, idempotent=False,
        )
        if final.status_code >= 400:
            raise _map(final.status_code, final.text)
        return media_id

    def media_status(self, media_id: str) -> dict[str, Any]:
        if self.dry_run:
            return {"media_id_string": media_id, "processing_info": {"state":"succeeded"}}
        resp = self._http.request(
            "GET", f"{UPLOAD}/media/upload.json",
            headers={"Authorization": f"Bearer {self.token}"},
            params={"command":"STATUS", "media_id":media_id}, idempotent=True,
        )
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        return resp.json() if resp.content else {}
