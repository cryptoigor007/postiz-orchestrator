"""Instagram module — Graph Content Publishing + B2 video_url.

v0.2.0: полный каркас API + dry-run. Live — после [ВЛАДЕЛЕЦ] токенов + B2.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ...http_client import ModuleHttpClient
from ..base import (
    AuthStatus,
    ClaimsResult,
    MediaSpec,
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
from ..manifest import ModuleManifest, load_manifest
from .api import InstagramApi

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class InstagramModule(PlatformModule):
    def __init__(
        self,
        *,
        access_token: str = "",
        ig_user_id: str = "",
        media_host: Any = None,
        http: ModuleHttpClient | None = None,
        dry_run: bool = True,
        account_label: str = "",
        poll_interval: float = 2.0,
        poll_max: int = 30,
        **_kw: Any,
    ) -> None:
        self.manifest: ModuleManifest = load_manifest(_MANIFEST)
        self._dry_run = bool(dry_run)
        self._account_label = account_label or "instagram"
        self._media_host = media_host
        self._poll_interval = poll_interval
        self._poll_max = poll_max
        tok = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        ig = ig_user_id or os.getenv("INSTAGRAM_USER_ID", "")
        self._api = InstagramApi(tok, ig, http=http, dry_run=dry_run)

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_label, details="dry-run")
        try:
            me = self._api.me()
            return AuthStatus(
                ok=True,
                account=str(me.get("username") or self._account_label),
                details=f"id={me.get('id')}",
            )
        except ModuleError as e:
            return AuthStatus(ok=False, account=self._account_label, details=e.message)

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        notes = []
        if media.kind == "video" and not self._media_host and not self._dry_run:
            notes.append("нужен media_host (B2) для public video_url")
        return PreparedMedia(path=media.path, kind=media.kind, notes=notes)

    def _video_url(self, media: PreparedMedia, meta: PublishMeta) -> str:
        extra = meta.extra or {}
        if extra.get("video_url"):
            return str(extra["video_url"])
        if self._media_host and media.path:
            return str(self._media_host.upload(media.path, prefix="ig"))
        if self._dry_run:
            return "https://example.invalid/dry-ig.mp4"
        raise ModuleError(
            ModuleErrorCode.MEDIA_INVALID,
            "нет публичного video_url и media_host",
            action="настройте B2 (P6.1) или передайте extra.video_url",
        )

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        caption = " ".join(
            x for x in [meta.title or "", meta.description or "", meta.hashtags or ""] if x
        ).strip()
        video_url = self._video_url(media, meta)
        cid = self._api.create_reels_container(video_url, caption)
        # poll container
        status = "IN_PROGRESS"
        for _ in range(self._poll_max):
            status = self._api.container_status(cid)
            if status in ("FINISHED", "ERROR", "EXPIRED"):
                break
            if self._dry_run:
                break
            time.sleep(self._poll_interval)
        if status == "EXPIRED":
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                "контейнер IG истёк",
                action="повторите publish ближе к слоту",
            )
        if status == "ERROR":
            raise ModuleError(
                ModuleErrorCode.PLATFORM_REJECTED,
                "контейнер IG в ERROR",
                action="проверьте video_url и формат 9:16",
            )
        mid = self._api.publish_container(cid)
        url = self._api.permalink(mid)
        return PublishResult(external_id=mid, url=url, state="published")

    def delete(self, external_id: str) -> bool:
        # IG delete optional scope — v1: not supported without instagram_manage_contents
        raise NotSupported("delete")

    def get_status(self, external_id: str) -> PublishStatus:
        if self._dry_run:
            return PublishStatus(state="published", url=f"https://www.instagram.com/reel/{external_id}/")
        try:
            url = self._api.permalink(external_id)
            return PublishStatus(state="published", url=url)
        except ModuleError as e:
            return PublishStatus(state="failed", error=e.message)

    def check_claims(self, external_id: str) -> ClaimsResult:
        return ClaimsResult(supported=False)

    def upload(self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None) -> UploadResult:
        # early container within 24h — same as create without publish
        caption = (meta.description or meta.title or "")[:2200]
        video_url = self._video_url(media, meta)
        cid = self._api.create_reels_container(video_url, caption)
        return UploadResult(external_id=cid, url="", state="uploaded")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        raise NotSupported("schedule_publish")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        raise NotSupported("update_metadata")


def create_instagram_module(**deps: Any) -> InstagramModule:
    return InstagramModule(**deps)
