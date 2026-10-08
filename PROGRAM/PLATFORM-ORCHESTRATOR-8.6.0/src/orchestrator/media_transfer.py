from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
import tempfile
import urllib.error
import urllib3
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Iterable
from urllib.parse import urlparse


@dataclass
class MediaArtifact:
    id: str
    path: str
    sha256: str
    size_bytes: int
    mime_type: str = ""
    kind: str = "video"
    remote_url: str = ""


class SSRFBlocked(ValueError):
    pass


class MediaTransferManager:
    """Shared media boundary: safe URL fetch, hashing, temp cleanup and chunks."""

    def __init__(self, db=None, *, temp_dir: str | Path | None = None, max_download_bytes: int = 2 * 1024**3):
        self.db = db
        self.temp_dir = Path(temp_dir or tempfile.gettempdir()) / "orchestrator-media"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.max_download_bytes = int(max_download_bytes)

    @staticmethod
    def _safe_ip(value: str) -> bool:
        ip = ipaddress.ip_address(value)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified)

    @classmethod
    def validate_url(cls, url: str) -> None:
        p = urlparse(url)
        if p.scheme not in {"https", "http"} or not p.hostname:
            raise SSRFBlocked("unsupported or malformed media URL")
        host = p.hostname.strip().lower()
        if host in {"localhost", "localhost.localdomain"}:
            raise SSRFBlocked("localhost blocked")
        try:
            answers = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except OSError as exc:
            raise SSRFBlocked(f"DNS resolution failed: {host}") from exc
        ips = {str(a[4][0]) for a in answers}
        if not ips or not all(cls._safe_ip(ip) for ip in ips):
            raise SSRFBlocked(f"private/reserved media host blocked: {host}")

    def _record(self, artifact: MediaArtifact, *, expires_at: str | None = None) -> None:
        if self.db is None:
            return
        now = datetime.now(UTC).isoformat()
        self.db.execute(
            "INSERT INTO media_artifacts(id,sha256,path,kind,mime_type,size_bytes,storage_provider,remote_url,created_at,expires_at,deleted_at) "
            "VALUES(?,?,?,?,?,?, 'local', ?, ?, ?, NULL) ON CONFLICT(id) DO NOTHING",
            (artifact.id, artifact.sha256, artifact.path, artifact.kind, artifact.mime_type, artifact.size_bytes,
             artifact.remote_url or None, now, expires_at),
        )

    def ingest_local(self, path: str | Path, *, kind: str = "video", mime_type: str = "") -> MediaArtifact:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(str(p))
        h = hashlib.sha256()
        size = 0
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
                size += len(chunk)
        artifact = MediaArtifact(uuid.uuid4().hex, str(p), h.hexdigest(), size, mime_type, kind)
        self._record(artifact)
        return artifact

    @classmethod
    def _resolve_public_ips(cls, url: str) -> tuple[str, int, list[str]]:
        p = urlparse(url)
        if p.scheme not in {"https", "http"} or not p.hostname:
            raise SSRFBlocked("unsupported or malformed media URL")
        host = p.hostname or ""
        port = p.port or (443 if p.scheme == "https" else 80)
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ips = sorted({str(a[4][0]) for a in answers})
        if not ips or not all(cls._safe_ip(ip) for ip in ips):
            raise SSRFBlocked(f"private/reserved media host blocked: {host}")
        return host, port, ips

    def fetch_url(self, url: str, *, kind: str = "video", mime_type: str = "", filename: str | None = None) -> MediaArtifact:
        current = url
        for _hop in range(4):
            # Single authoritative DNS resolution for this hop.
            # _resolve_public_ips validates every resolved address before any socket connect,
            # and the resulting IP list is pinned for the actual HTTP request.
            host, port, pinned_ips = self._resolve_public_ips(current)
            parsed = urlparse(current)
            target = parsed.path or "/"
            if parsed.query:
                target += "?" + parsed.query
            headers = {"User-Agent": "orchestrator-media/1.0", "Host": host}
            resp = None
            pool = None
            try:
                last_exc: Exception | None = None
                for ip in pinned_ips:
                    try:
                        if parsed.scheme == "https":
                            pool = urllib3.HTTPSConnectionPool(
                                ip, port, assert_hostname=host, server_hostname=host,
                                cert_reqs="CERT_REQUIRED", headers=headers,
                            )
                        else:
                            pool = urllib3.HTTPConnectionPool(ip, port, headers=headers)
                        resp = pool.request("GET", target, preload_content=False, timeout=30, redirect=False)
                        last_exc = None
                        break
                    except Exception as exc:
                        last_exc = exc
                        if pool is not None:
                            pool.close()
                        pool = None
                if resp is None:
                    raise RuntimeError(f"all pinned media endpoints failed: {last_exc}")
                status = int(getattr(resp, "status", 200) or 200)
                if status in {301, 302, 303, 307, 308}:
                    redirect = resp.headers.get("Location")
                    if not redirect:
                        raise SSRFBlocked("redirect without Location")
                    current = urllib.parse.urljoin(current, redirect) if not redirect.startswith(("http://", "https://")) else redirect
                    continue
                if status >= 400:
                    raise RuntimeError(f"media fetch HTTP {status}")
                out = self.temp_dir / (filename or f"{uuid.uuid4().hex}.bin")
                h = hashlib.sha256()
                size = 0
                try:
                    with out.open("wb") as fh:
                        while True:
                            chunk = resp.read(1024 * 1024)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > self.max_download_bytes:
                                out.unlink(missing_ok=True)
                                raise ValueError("media download exceeds configured limit")
                            h.update(chunk)
                            fh.write(chunk)
                finally:
                    resp.release_conn()
                    if pool is not None:
                        pool.close()
                artifact = MediaArtifact(
                    uuid.uuid4().hex, str(out), h.hexdigest(), size,
                    mime_type or str(resp.headers.get("Content-Type", "").split(";", 1)[0]),
                    kind, current,
                )
                self._record(artifact)
                return artifact
            except (urllib.error.URLError, urllib3.exceptions.HTTPError, OSError) as exc:
                raise RuntimeError(f"media fetch failed: {exc}") from exc
            finally:
                if pool is not None:
                    pool.close()
        raise SSRFBlocked("too many media redirects")

    @staticmethod
    def iter_chunks(path: str | Path, *, chunk_size: int = 8 * 1024 * 1024) -> Iterable[tuple[int, bytes]]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        offset = 0
        with Path(path).open("rb") as fh:
            while True:
                data = fh.read(chunk_size)
                if not data:
                    return
                yield offset, data
                offset += len(data)

    def cleanup_orphans(self, *, older_than_sec: int = 86400, active_paths: set[str] | None = None) -> int:
        active_paths = active_paths or set()
        cutoff = datetime.now(UTC).timestamp() - int(older_than_sec)
        removed = 0
        for row in (self.db.fetchall("SELECT id,path FROM media_artifacts WHERE deleted_at IS NULL") if self.db else []):
            path = str(row.get("path") or "")
            if not path or path in active_paths:
                continue
            try:
                if Path(path).exists() and Path(path).stat().st_mtime > cutoff:
                    continue
                Path(path).unlink(missing_ok=True)
            except OSError:
                continue
            if self.db:
                self.db.execute("UPDATE media_artifacts SET deleted_at=? WHERE id=?", (datetime.now(UTC).isoformat(), row["id"]))
            removed += 1
        return removed
