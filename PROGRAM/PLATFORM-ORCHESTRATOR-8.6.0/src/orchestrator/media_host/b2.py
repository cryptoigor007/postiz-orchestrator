"""Backblaze B2: streaming upload → public URL → delete(fileId, fileName).

TTL ≤ 24h via media_host_objects + cleanup job helper.
Without live keys: dry_run. Unit tests inject HTTP transport.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MiB streaming reads


class B2MediaHost:
    """B2 client: authorize → upload (streamed) → public url → delete(fileId, fileName)."""

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
        db: Any = None,
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
        self._uploaded: list[tuple[str, str]] = []  # (file_id, file_name)
        self.db = db

    @property
    def configured(self) -> bool:
        return bool(self.key_id and self.app_key and (self.bucket_id or self.bucket_name))

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=120.0, transport=self._transport)

    def authorize(self) -> dict[str, Any]:
        if self.dry_run:
            self._auth = {
                "authorizationToken": "dry",
                "apiUrl": "https://api.dry.invalid",
                "downloadUrl": "https://f000.dry.invalid",
            }
            return self._auth
        if not self.key_id or not self.app_key:
            raise RuntimeError("B2_KEY_ID / B2_APPLICATION_KEY not set")
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

    def _sha1_stream(self, fh: BinaryIO) -> tuple[str, int]:
        h = hashlib.sha1()
        total = 0
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
            total += len(chunk)
        return h.hexdigest(), total

    def upload(
        self,
        path: str | Path,
        *,
        prefix: str = "tmp",
        entity_type: str | None = None,
        entity_id: int | None = None,
        platform: str | None = None,
    ) -> str:
        """Upload file (streamed hash + content), return public URL. Records media_host_objects."""
        p = Path(path)
        if not p.is_file() and not self.dry_run:
            raise FileNotFoundError(str(p))
        ext = p.suffix or ".bin"
        name = f"{prefix}/{int(time.time())}_{secrets.token_hex(8)}{ext}"

        if self.dry_run:
            url = f"https://f000.dry.invalid/file/{self.bucket_name or 'bucket'}/{name}"
            fid = f"dry:{name}"
            self._uploaded.append((fid, name))
            self._record_object(fid, name, url, entity_type, entity_id, platform)
            logger.info("B2 dry-run upload %s → %s", p.name, url)
            return url

        auth = self._ensure_auth()
        api = auth["apiUrl"]
        token = auth["authorizationToken"]
        with self._client() as c:
            r = c.post(
                f"{api}/b2api/v2/b2_get_upload_url",
                headers={"Authorization": token},
                json={"bucketId": self.bucket_id},
            )
            r.raise_for_status()
            up = r.json()
            upload_url = up["uploadUrl"]
            upload_token = up["authorizationToken"]

            with p.open("rb") as fh:
                sha, size = self._sha1_stream(fh)
                fh.seek(0)
                # stream body in chunks via generator to avoid full second buffer when possible
                def _gen():
                    while True:
                        chunk = fh.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk

                r2 = c.post(
                    upload_url,
                    headers={
                        "Authorization": upload_token,
                        "X-Bz-File-Name": quote(name),
                        "Content-Type": "b2/x-auto",
                        "X-Bz-Content-Sha1": sha,
                        "Content-Length": str(size),
                    },
                    content=_gen(),
                )
            r2.raise_for_status()
            info = r2.json()
            file_id = info.get("fileId", "") or ""
            file_name = info.get("fileName", name) or name
            if file_id:
                self._uploaded.append((file_id, file_name))
            download = auth.get("downloadUrl", "").rstrip("/")
            url = f"{download}/file/{self.bucket_name}/{file_name}"
            self._record_object(file_id, file_name, url, entity_type, entity_id, platform)
            return url

    def _record_object(
        self,
        file_id: str,
        file_name: str,
        url: str,
        entity_type: str | None,
        entity_id: int | None,
        platform: str | None,
    ) -> None:
        if self.db is None or not file_id:
            return
        try:
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            exp = now + timedelta(seconds=self.ttl_sec)
            self.db.execute(
                """
                INSERT INTO media_host_objects
                    (provider, file_id, file_name, url, entity_type, entity_id,
                     platform, created_at, expires_at, status)
                VALUES ('b2', ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    file_id, file_name, url, entity_type, entity_id, platform,
                    now.isoformat(), exp.isoformat(),
                ),
            )
        except Exception:
            logger.debug("media_host_objects insert failed", exc_info=True)

    def delete(self, file_id: str, file_name: str | None = None) -> bool:
        """Delete by real fileId + fileName (B2 requires both)."""
        if self.dry_run or (file_id or "").startswith("dry:"):
            if (file_id or "").startswith("dry:") and not file_name:
                file_name = file_id.split(":", 1)[-1]
            self._mark_deleted(file_id)
            return True
        if not file_id:
            return False
        # resolve name from upload list or DB
        if not file_name:
            for fid, fname in self._uploaded:
                if fid == file_id:
                    file_name = fname
                    break
        if not file_name and self.db is not None:
            try:
                row = self.db.fetchone(
                    "SELECT file_name FROM media_host_objects WHERE file_id=? AND deleted_at IS NULL",
                    (file_id,),
                )
                if row:
                    file_name = row["file_name"]
            except Exception:
                logger.debug("B2 metadata lookup failed for %s", file_id, exc_info=True)
        if not file_name:
            logger.warning("B2 delete: missing fileName for %s", file_id)
            return False
        auth = self._ensure_auth()
        try:
            with self._client() as c:
                r = c.post(
                    f"{auth['apiUrl']}/b2api/v2/b2_delete_file_version",
                    headers={"Authorization": auth["authorizationToken"]},
                    json={"fileId": file_id, "fileName": file_name},
                )
                ok = r.status_code < 400
                if ok:
                    self._mark_deleted(file_id)
                return ok
        except Exception as e:
            logger.warning("B2 delete %s / %s: %s", file_id, file_name, e)
            return False

    def _mark_deleted(self, file_id: str) -> None:
        if self.db is None:
            return
        try:
            from datetime import datetime, timezone
            self.db.execute(
                "UPDATE media_host_objects SET deleted_at=?, status='deleted' "
                "WHERE file_id=? AND deleted_at IS NULL",
                (datetime.now(timezone.utc).isoformat(), file_id),
            )
        except Exception:
            logger.debug("mark deleted failed", exc_info=True)

    def cleanup_expired(self) -> int:
        """Delete objects past expires_at (TTL job)."""
        if self.db is None:
            return self.cleanup_all()
        n = 0
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            rows = self.db.fetchall(
                "SELECT file_id, file_name FROM media_host_objects "
                "WHERE deleted_at IS NULL AND expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            for r in rows or []:
                if self.delete(r["file_id"], r["file_name"]):
                    n += 1
        except Exception:
            logger.debug("cleanup_expired failed", exc_info=True)
        return n

    def cleanup_all(self) -> int:
        n = 0
        for fid, fname in list(self._uploaded):
            if self.delete(fid, fname):
                n += 1
                self._uploaded = [(a, b) for a, b in self._uploaded if a != fid]
        return n

    def head_url(self, url: str) -> int | None:
        """HEAD/curl -I verification helper; returns status code or None."""
        if self.dry_run:
            return 200
        try:
            with self._client() as c:
                r = c.head(url)
                return r.status_code
        except Exception:
            return None


def create_media_host(*, dry_run: bool = False, **kwargs: Any) -> B2MediaHost:
    return B2MediaHost(dry_run=dry_run, **kwargs)
