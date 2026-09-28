"""Threads module v0.2.0 — dry-run container/publish; live needs B2 + Meta."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ...http_client import ModuleHttpClient
from ..base import (
    AuthStatus,
    ClaimsResult,
    NotSupported,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    PublishStatus,
    UploadResult,
)
from ..manifest import load_manifest
from .api import ThreadsApi

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class ThreadsModule(PlatformModule):
    def __init__(self, *, access_token: str = "", user_id: str = "", media_host: Any = None, http: ModuleHttpClient | None = None, dry_run: bool = True, account_label: str = "", **_kw: Any):
        self.manifest = load_manifest(_MANIFEST)
        self._dry_run = dry_run
        self._account_label = account_label or "threads"
        self._media_host = media_host
        tok = access_token or os.getenv("THREADS_ACCESS_TOKEN", "")
        uid = user_id or os.getenv("THREADS_USER_ID", "")
        self._api = ThreadsApi(tok, uid, http=http, dry_run=dry_run)

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_label, details="dry-run")
        return AuthStatus(ok=False, account=self._account_label, details="live token required")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        text = " ".join(x for x in [meta.title, meta.description] if x).strip()
        extra = meta.extra or {}
        video_url = str(extra.get("video_url") or "")
        image_url = str(extra.get("image_url") or "")
        if self._media_host and media.path and not video_url and not image_url:
            video_url = self._media_host.upload(media.path, prefix="th")
        cid = self._api.create_container(text=text, video_url=video_url, image_url=image_url)
        pid = self._api.publish(cid)
        return PublishResult(external_id=pid, url="", state="published")

    def delete(self, external_id: str) -> bool:
        if self._dry_run:
            return True
        raise NotSupported("delete")

    def get_status(self, external_id: str) -> PublishStatus:
        return PublishStatus(state="published" if self._dry_run else "failed")

    def check_claims(self, external_id: str) -> ClaimsResult:
        return ClaimsResult(supported=False)

    def upload(self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None) -> UploadResult:
        raise NotSupported("upload")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        raise NotSupported("schedule_publish")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        raise NotSupported("update_metadata")


def create_threads_module(**deps: Any) -> ThreadsModule:
    return ThreadsModule(**deps)
