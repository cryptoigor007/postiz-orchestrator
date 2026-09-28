"""Facebook Page module v0.2.0 — dry-run Graph feed/videos."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ...http_client import ModuleHttpClient
from ..base import (
    AuthStatus,
    ClaimsResult,
    ModuleError,
    ModuleErrorCode,
    NotSupported,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    PublishStatus,
    UploadResult,
)
from ..manifest import load_manifest
from .api import FacebookApi

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class FacebookModule(PlatformModule):
    def __init__(
        self,
        *,
        page_token: str = "",
        page_id: str = "",
        http: ModuleHttpClient | None = None,
        dry_run: bool = True,
        account_label: str = "",
        **_kw: Any,
    ) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self._dry_run = dry_run
        self._account_label = account_label or "facebook"
        tok = page_token or os.getenv("FACEBOOK_PAGE_TOKEN", "")
        pid = page_id or os.getenv("FACEBOOK_PAGE_ID", "")
        self._api = FacebookApi(tok, pid, http=http, dry_run=dry_run)

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_label, details="dry-run")
        try:
            info = self._api.page_info()
            return AuthStatus(ok=True, account=str(info.get("name") or self._account_label))
        except ModuleError as e:
            return AuthStatus(ok=False, account=self._account_label, details=e.message)

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        text = " ".join(x for x in [meta.title, meta.description, meta.hashtags] if x).strip()
        extra = meta.extra or {}
        link = str(extra.get("link") or extra.get("url") or "")
        file_url = str(extra.get("file_url") or extra.get("video_url") or "")
        if file_url or (media.path and media.kind == "video" and extra.get("use_file_url")):
            oid = self._api.video_post(file_url or "https://example.invalid/v.mp4", text)
        else:
            oid = self._api.feed_post(text or " ", link)
        if not oid:
            raise ModuleError(ModuleErrorCode.FATAL, "Facebook не вернул id", action="логи")
        return PublishResult(external_id=oid, url=f"https://www.facebook.com/{oid}", state="published")

    def delete(self, external_id: str) -> bool:
        return self._api.delete(external_id)

    def get_status(self, external_id: str) -> PublishStatus:
        return PublishStatus(state="published", url=f"https://www.facebook.com/{external_id}")

    def check_claims(self, external_id: str) -> ClaimsResult:
        return ClaimsResult(supported=False)

    def upload(self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None) -> UploadResult:
        raise NotSupported("upload")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        raise NotSupported("schedule_publish")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        raise NotSupported("update_metadata")


def create_facebook_module(**deps: Any) -> FacebookModule:
    return FacebookModule(**deps)
