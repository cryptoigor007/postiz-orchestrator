from __future__ import annotations

import os
import struct
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ...http_client import ModuleHttpClient
from ..base import (
    AuthStatus,
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    PublishStatus,
    RemoteItem,
    RemotePage,
)
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")


def _image_info(path: Path) -> tuple[str, int, int]:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return "png", w, h
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        w, h = struct.unpack("<HH", data[6:10])
        return "gif", w, h
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            while i < len(data) and data[i] == 0xFF:
                i += 1
            if i >= len(data):
                break
            marker = data[i]
            i += 1
            if marker in (0xD8, 0xD9):
                continue
            if i + 2 > len(data):
                break
            seg_len = struct.unpack(">H", data[i:i+2])[0]
            if seg_len < 2 or i + seg_len > len(data):
                break
            if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
                h, w = struct.unpack(">HH", data[i+3:i+7])
                return "jpeg", w, h
            i += seg_len
    raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Dribbble: unsupported or invalid image; expected GIF/JPEG/PNG")


class DribbbleModule(PlatformModule):
    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base = str(deps.get("base_url") or os.getenv("DRIBBBLE_API_BASE", "https://api.dribbble.com/v2")).rstrip("/")
        self.token = str(deps.get("access_token") or os.getenv("DRIBBBLE_ACCESS_TOKEN", "")).strip()
        self.team_id = str(deps.get("team_id") or os.getenv("DRIBBBLE_TEAM_ID", "")).strip()
        self._http = deps.get("http") or ModuleHttpClient(platform="dribbble", module_version=self.manifest.module_version)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    @staticmethod
    def _error(status: int, action: str) -> ModuleError:
        code = ModuleErrorCode.AUTH_EXPIRED if status in (401, 403) else ModuleErrorCode.RATE_LIMIT if status == 429 else ModuleErrorCode.TRANSIENT if status >= 500 else ModuleErrorCode.PLATFORM_REJECTED
        return ModuleError(code, f"Dribbble {action} HTTP {status}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def auth_status(self) -> AuthStatus:
        if not self.token:
            return AuthStatus(False, account="dribbble", details="DRIBBBLE_ACCESS_TOKEN missing")
        r = self._http.request("GET", f"{self.base}/user", headers=self._headers())
        if r.status_code >= 400:
            return AuthStatus(False, account="dribbble", details=f"/user HTTP {r.status_code}")
        d = r.json() if r.content else {}
        return AuthStatus(True, account=str(d.get("username") or d.get("name") or "dribbble"), details="/user ok")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        return [] if self.token else ["dribbble: DRIBBBLE_ACCESS_TOKEN required"]

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        if media.kind != "image":
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Dribbble: only image content is supported")
        p = Path(media.path)
        if not p.is_file():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"Dribbble: file not found: {p}")
        if p.stat().st_size > 8 * 1024 * 1024:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Dribbble: image must be <= 8 MB")
        kind, w, h = _image_info(p)
        if (w, h) not in {(400, 300), (800, 600)}:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"Dribbble: image dimensions must be 400x300 or 800x600, got {w}x{h}")
        return PreparedMedia(media.path, "image")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if not self.token:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Dribbble: access token required")
        p = Path(media.path)
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif"}.get(p.suffix.lower(), "application/octet-stream")
        data: dict[str, Any] = {"title": str(meta.title or p.stem)[:120], "description": str(meta.description or "")}
        tags = [x.lstrip("#") for x in str(meta.hashtags or "").split() if x.strip()][:12]
        if tags:
            data["tags[]"] = tags
        extra = dict(meta.extra or {})
        for key in ("scheduled_for", "low_profile", "team_id"):
            if extra.get(key) is not None:
                data[key] = extra[key]
        if self.team_id and "team_id" not in data:
            data["team_id"] = self.team_id
        with p.open("rb") as fh:
            r = self._http.request("POST", f"{self.base}/shots", headers=self._headers(), data=data, files={"image": (p.name, fh, mime)}, idempotent=False, upload=True)
        if r.status_code >= 400:
            raise self._error(r.status_code, "create shot")
        d = r.json() if r.content else {}
        rid = str(d.get("id") or "")
        if not rid:
            loc = str(r.headers.get("location") or "")
            rid = urlparse(loc).path.rstrip("/").split("/")[-1] if loc else ""
        if not rid:
            raise ModuleError(ModuleErrorCode.FATAL, "Dribbble: create shot returned no id/location")
        return PublishResult(external_id=rid, url=str(d.get("html_url") or d.get("url") or ""), state="processing")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        return self.update_metadata(external_id, PublishMeta(extra={"scheduled_for": when.isoformat()}))

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        data: dict[str, Any] = {}
        if patch.title:
            data["title"] = patch.title[:120]
        if patch.description is not None:
            data["description"] = patch.description
        tags = [x.lstrip("#") for x in str(patch.hashtags or "").split() if x.strip()][:12]
        if tags:
            data["tags[]"] = tags
        for key in ("scheduled_for", "low_profile", "team_id"):
            if (patch.extra or {}).get(key) is not None:
                data[key] = patch.extra[key]
        r = self._http.request("PUT", f"{self.base}/shots/{external_id}", headers=self._headers(), data=data, idempotent=True)
        if r.status_code >= 400:
            raise self._error(r.status_code, "update shot")
        return True

    def get_status(self, external_id: str) -> PublishStatus:
        r = self._http.request("GET", f"{self.base}/shots/{external_id}", headers=self._headers())
        if r.status_code == 404:
            return PublishStatus(state="processing", raw={"reason": "Dribbble may return 404 while a new shot is still processing"})
        if r.status_code >= 400:
            raise self._error(r.status_code, "get shot")
        d = r.json() if r.content else {}
        return PublishStatus(state="published", url=str(d.get("html_url") or d.get("url") or ""), raw=d)

    def delete(self, external_id: str) -> bool:
        r = self._http.request("DELETE", f"{self.base}/shots/{external_id}", headers=self._headers(), idempotent=True)
        if r.status_code == 404:
            return True
        if r.status_code >= 400:
            raise self._error(r.status_code, "delete shot")
        return True

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        page = max(1, int(cursor or "1"))
        per_page = min(max(1, int(limit)), 100)
        r = self._http.request("GET", f"{self.base}/user/shots", headers=self._headers(), params={"page": page, "per_page": per_page})
        if r.status_code >= 400:
            raise self._error(r.status_code, "list shots")
        rows = r.json() if r.content else []
        if isinstance(rows, dict):
            rows = rows.get("shots") or rows.get("data") or []
        items = [RemoteItem(platform="dribbble", external_id=str(x.get("id") or ""), url=str(x.get("html_url") or ""), title=str(x.get("title") or ""), status="published", media_type="image", raw=x) for x in rows if isinstance(x, dict) and x.get("id")]
        return RemotePage(items=items, next_cursor=str(page + 1) if len(items) >= per_page else None)


def create_module(**deps: Any) -> DribbbleModule:
    return DribbbleModule(**deps)
