"""Backblaze B2: upload → public URL → delete (TTL ≤ 24 ч).

Без живых ключей работает в dry_run. Unit — injectable HTTP.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class B2MediaHost:
    """Минимальный клиент B2: authorize → upload → get public url → delete."""

    def __init__(
        self,
        *,
        key_id: str = "",
        app_key: str = "",
        bucket_id: str = "",
        bucket_name: str = "",
        endpoint: str = "",
        dry_run: bool = False,
        transport: httpx.BaseTransport | None = None,
        ttl_sec: int = 24 * 3600,
    ) -> None:
        self.key_id = key_id or os.getenv("B2_KEY_ID", "")
        self.app_key = app_key or os.getenv("B2_APPLICATION_KEY", "")
        self.bucket_id = bucket_id or os.getenv("B2_BUCKET_ID", "")
        self.bucket_name = bucket_name or os.getenv("B2_BUCKET", "")
        self.endpoint = (endpoint or os.getenv("B2_ENDPOINT", "")).rstrip("/")
        self.dry_run = bool(dry_run)
        self.ttl_sec = int(ttl_sec)
        self._transport = transport
        self._auth: dict[str, Any] | None = None
        self._uploaded: list[str] = []  # file_id for cleanup

    @property
    def configured(self) -> bool:
        return bool(self.key_id and self.app_key and (self.bucket_id or self.bucket_name))

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=60.0, transport=self._transport)

    def authorize(self) -> dict[str, Any]:
        if self.dry_run:
            self._auth = {
                "authorizationToken": "dry",
                "apiUrl": "https://api.dry.invalid",
                "downloadUrl": "https://f000.dry.invalid",
            }
            return self._auth
        if not self.key_id or not self.app_key:
            raise RuntimeError("B2_KEY_ID / B2_APPLICATION_KEY не заданы")
        with self._client() as c:
            r = c.get(
                "https://api.backblazeb2.com/b2api/v2/b2_authorize_account",
                auth=(self.key_id, self.app_key),
            )
            r.raise_for_status()
            self._auth = r.json()
            return self._auth

    def _ensure_auth(self) -> dict[str, Any]:
        if not self._auth:
            return self.authorize()
        return self._auth

    def upload(self, path: str | Path, *, prefix: str = "tmp") -> str:
        """Загрузить файл, вернуть публичный URL. Имя — случайное."""
        p = Path(path)
        if not p.is_file() and not self.dry_run:
            raise FileNotFoundError(str(p))
        ext = p.suffix or ".bin"
        name = f"{prefix}/{int(time.time())}_{secrets.token_hex(8)}{ext}"

        if self.dry_run:
            url = f"https://f000.dry.invalid/file/{self.bucket_name or 'bucket'}/{name}"
            self._uploaded.append(f"dry:{name}")
            logger.info("B2 dry-run upload %s → %s", p.name, url)
            return url

        auth = self._ensure_auth()
        api = auth["apiUrl"]
        token = auth["authorizationToken"]
        with self._client() as c:
            # get upload url
            r = c.post(
                f"{api}/b2api/v2/b2_get_upload_url",
                headers={"Authorization": token},
                json={"bucketId": self.bucket_id},
            )
            r.raise_for_status()
            up = r.json()
            upload_url = up["uploadUrl"]
            upload_token = up["authorizationToken"]
            data = p.read_bytes()
            import hashlib

            sha = hashlib.sha1(data).hexdigest()
            r2 = c.post(
                upload_url,
                headers={
                    "Authorization": upload_token,
                    "X-Bz-File-Name": quote(name),
                    "Content-Type": "b2/x-auto",
                    "X-Bz-Content-Sha1": sha,
                    "Content-Length": str(len(data)),
                },
                content=data,
            )
            r2.raise_for_status()
            info = r2.json()
            file_id = info.get("fileId", "")
            if file_id:
                self._uploaded.append(file_id)
            download = auth.get("downloadUrl", "").rstrip("/")
            url = f"{download}/file/{self.bucket_name}/{name}"
            return url

    def delete(self, file_id: str) -> bool:
        if self.dry_run or file_id.startswith("dry:"):
            return True
        if not file_id:
            return False
        auth = self._ensure_auth()
        try:
            with self._client() as c:
                r = c.post(
                    f"{auth['apiUrl']}/b2api/v2/b2_delete_file_version",
                    headers={"Authorization": auth["authorizationToken"]},
                    json={"fileId": file_id, "fileName": "x"},
                )
                return r.status_code < 400
        except Exception as e:
            logger.warning("B2 delete %s: %s", file_id, e)
            return False

    def cleanup_all(self) -> int:
        n = 0
        for fid in list(self._uploaded):
            if self.delete(fid):
                n += 1
                self._uploaded.remove(fid)
        return n


def create_media_host(*, dry_run: bool = False, **kwargs: Any) -> B2MediaHost:
    return B2MediaHost(dry_run=dry_run, **kwargs)
