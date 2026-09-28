"""TikTok module v0.2.0 — dry-run + creator_info; live [ЖДЁТ] audit."""

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
from .api import TikTokApi

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class TikTokModule(PlatformModule):
    def __init__(self, *, access_token: str = "", http: ModuleHttpClient | None = None, dry_run: bool = True, account_label: str = "", **_kw: Any):
        self.manifest = load_manifest(_MANIFEST)
        self._dry_run = dry_run
        self._account_label = account_label or "tiktok"
        tok = access_token or os.getenv("TIKTOK_ACCESS_TOKEN", "")
        self._api = TikTokApi(tok, http=http, dry_run=dry_run)

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_label, details="dry-run")
        try:
            info = self._api.creator_info()
            return AuthStatus(ok=True, account=str(info.get("creator_username") or self._account_label))
        except ModuleError as e:
            return AuthStatus(ok=False, account=self._account_label, details=e.message)

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if not self._dry_run:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "TikTok live: нужен audit + token", action="P7 + [ВЛАДЕЛЕЦ]")
        init = self._api.init_upload(0, meta.title or "")
        pid = str(init.get("publish_id") or "tt-dry")
        return PublishResult(external_id=pid, url="", state="published")

    def delete(self, external_id: str) -> bool:
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


def create_tiktok_module(**deps: Any) -> TikTokModule:
    return TikTokModule(**deps)
