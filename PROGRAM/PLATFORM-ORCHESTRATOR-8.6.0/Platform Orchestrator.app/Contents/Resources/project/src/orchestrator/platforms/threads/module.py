"""Threads module — video + text, publish at slot, list /me/threads, daily_limit default 3."""
from __future__ import annotations

import logging

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from ...http_client import ModuleHttpClient
from ..base import (
    AuthStatus, ClaimsResult, MediaSpec, ModuleError, ModuleErrorCode, NotSupported,
    PlatformModule, PreparedMedia, PublishMeta, PublishResult, PublishStatus, UploadResult,
)
from ..manifest import load_manifest
from .api import ThreadsApi

_MANIFEST = Path(__file__).with_name("manifest.yaml")


logger = logging.getLogger(__name__)

class ThreadsModule(PlatformModule):
    def __init__(
        self,
        *,
        access_token: str = "",
        user_id: str = "",
        http: ModuleHttpClient | None = None,
        dry_run: bool = True,
        account_label: str = "",
        media_host: Any = None,
        cache_dir: str = "",
        token_provider: Any = None,
        api_version: str = "",
        **_kw: Any,
    ) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self._dry_run = dry_run
        self._account_label = account_label or "threads"
        self._media_host = media_host
        self._cache_dir = cache_dir or os.getenv("ORCH_THREADS_CACHE", "/tmp/orch_threads_cache")
        tok = access_token or os.getenv("THREADS_ACCESS_TOKEN", "")
        if not tok and callable(token_provider):
            try:
                tok = token_provider("threads") or ""
            except Exception:
                tok = ""
        uid = user_id or os.getenv("THREADS_USER_ID", "")
        self._api = ThreadsApi(tok, uid, http=http, dry_run=dry_run, api_version=api_version or os.getenv("THREADS_API_VERSION") or "v1.0")

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_label, details="dry-run")
        try:
            me = self._api.me() if hasattr(self._api, "me") else {"id": "x"}
            return AuthStatus(ok=True, account=str(me.get("username") or self._account_label))
        except Exception as e:
            return AuthStatus(ok=False, account=self._account_label, details=str(e))

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        path = media.path or ""
        notes: list[str] = []
        if path and media.kind == "video":
            fast = self._ensure_faststart(path)
            if fast != path:
                path = fast
                notes.append("faststart_remux")
        return PreparedMedia(path=path, kind=media.kind or "video", notes=notes)

    def _ensure_faststart(self, path: str) -> str:
        """Remux +cache for streaming; best-effort ffmpeg."""
        try:
            Path(self._cache_dir).mkdir(parents=True, exist_ok=True)
            out = str(Path(self._cache_dir) / (Path(path).stem + "_fs.mp4"))
            if Path(out).is_file() and Path(out).stat().st_mtime >= Path(path).stat().st_mtime:
                return out
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-c", "copy", "-movflags", "+faststart", out],
                check=True, capture_output=True, timeout=120,
            )
            return out if Path(out).is_file() else path
        except Exception:
            return path

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        text = " ".join(x for x in [meta.title or "", meta.description or ""] if x).strip()
        video_url = ""
        image_url = ""
        if media.path and media.kind in {"video", "image"}:
            if self._media_host:
                prefix = "th" + ("-img" if media.kind == "image" else "")
                hosted = str(self._media_host.upload(media.path, prefix=prefix))
                if media.kind == "image":
                    image_url = hosted
                else:
                    video_url = hosted
            elif self._dry_run:
                if media.kind == "image": image_url = "https://example.invalid/dry-th.jpg"
                else: video_url = "https://example.invalid/dry-th.mp4"
            else:
                raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "need media_host for Threads media")
        cid = self._api.create_container(text=text, video_url=video_url, image_url=image_url)
        # If the provider requires processing, fail explicitly instead of claiming publish.
        try:
            st = self._api.container_status(cid)
            status = str(st.get("status") or "FINISHED").upper()
            if not self._dry_run and status not in {"FINISHED", "PUBLISHED", "READY"}:
                raise ModuleError(ModuleErrorCode.TRANSIENT, f"Threads container status={status}", retryable=True)
        except AttributeError:
            logger.debug("Threads container status helper unavailable", exc_info=True)
        pid = self._api.publish(cid)
        url = ""
        try:
            obj = self._api.get(pid)
            url = str(obj.get("permalink") or "")
        except Exception as exc:
            logger.warning("Threads post lookup after publish failed: %s", type(exc).__name__)
        return PublishResult(external_id=pid, url=url, state="published")

    def upload(self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None) -> UploadResult:
        raise NotSupported("early_upload")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        raise NotSupported("schedule_publish")

    def get_status(self, external_id: str) -> PublishStatus:
        # N13: do not claim authoritative published without API confirmation
        if self._dry_run:
            return PublishStatus(state="published", url="")
        try:
            data = self._api.get(external_id)
            return PublishStatus(state="published", url=str(data.get("permalink") or ""))
        except Exception as exc:
            return PublishStatus(state="unknown", url="", error=str(exc)[:300])

    def delete(self, external_id: str) -> bool:
        return self._api.delete(external_id)

    def get_quota(self):
        from ..base import QuotaSnapshot
        body = self._api.publishing_limit()
        config = body.get("quota_config") or {}
        return QuotaSnapshot(unit="posts", remaining=max(int(config.get("quota_total") or 0) - int(body.get("quota_usage") or 0), 0) if config else None, limit=int(config.get("quota_total") or 0) or None, raw=body)

    def list_remote(self, *, limit: int = 25) -> list[dict]:
        if self._dry_run:
            return []
        if hasattr(self._api, "list_threads"):
            items = self._api.list_threads(limit=limit)
            return [{"external_id": i.get("id"), "status": "published", "title": (i.get("text") or "")[:80]} for i in items]
        return []

    def check_claims(self, external_id: str) -> ClaimsResult:
        return ClaimsResult(supported=False)

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        raise NotSupported("update_metadata")



    def list_remote_items(
        self,
        *,
        kinds: set[str] | None = None,
        since=None,
        until=None,
        limit: int = 50,
        cursor: str | None = None,
    ):
        """Adapter: modules exposing list_remote() satisfy RemoteScan contract."""
        from ..base import RemoteItem, RemotePage
        try:
            raw = self.list_remote(limit=limit)
        except Exception as exc:
            logger.warning("threads list_remote failed: %s", type(exc).__name__)
            return RemotePage(items=[], partial=True, notes=[f"list_remote failed: {type(exc).__name__}"])
        items = []
        for it in raw or []:
            if not isinstance(it, dict):
                continue
            items.append(RemoteItem(
                platform="threads",
                external_id=str(it.get("id") or it.get("external_id") or ""),
                title=str(it.get("title") or ""),
                status=str(it.get("status") or "published"),
                url=str(it.get("url") or it.get("link") or ""),
            ))
        return RemotePage(items=items, partial=True, notes=["via list_remote"])

def create_threads_module(**deps: Any) -> ThreadsModule:
    return ThreadsModule(**deps)
