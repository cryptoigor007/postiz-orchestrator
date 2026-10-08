"""Instagram module — Graph Content Publishing + B2 video_url.

v0.2.0: полный каркас API + dry-run. Live — после [ВЛАДЕЛЕЦ] токенов + B2.
"""

from __future__ import annotations

import logging
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
logger = logging.getLogger(__name__)


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
        token_provider: Any = None,
        cfg: Any = None,
        **_kw: Any,
    ) -> None:
        self.manifest: ModuleManifest = load_manifest(_MANIFEST)
        self._dry_run = bool(dry_run)
        self._account_label = account_label or "instagram"
        self._media_host = media_host
        self._poll_interval = poll_interval
        self._poll_max = poll_max
        tok = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        if not tok and callable(token_provider):
            try:
                tok = token_provider("instagram") or ""
            except Exception:
                tok = ""
        if not ig_user_id and cfg is not None:
            pcfg = (getattr(cfg, "platforms", {}) or {}).get("instagram")
            ig_user_id = getattr(pcfg, "channel_id", "") or ig_user_id
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

    def _media_url(self, media: PreparedMedia, meta: PublishMeta) -> str:
        extra = meta.extra or {}
        key = "image_url" if media.kind == "image" else "video_url"
        if extra.get(key):
            return str(extra[key])
        if self._media_host and media.path:
            return str(self._media_host.upload(media.path, prefix="ig-img" if media.kind == "image" else "ig"))
        if self._dry_run:
            return "https://example.invalid/dry-ig.jpg" if media.kind == "image" else "https://example.invalid/dry-ig.mp4"
        raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "нет публичного media_url и media_host", action="настройте media_host или передайте extra.image_url/video_url")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        caption = " ".join(x for x in [meta.title or "", meta.description or "", meta.hashtags or ""] if x).strip()
        extra = meta.extra or {}
        carousel = extra.get("carousel_image_urls")
        if isinstance(carousel, (list, tuple)):
            children: list[str] = []
            for idx, image_url in enumerate(carousel[:10]):
                children.append(self._api.create_image_container(str(image_url), caption=""))
            cid = self._api.create_carousel_container(children, caption)
        elif media.kind == "image":
            cid = self._api.create_image_container(self._media_url(media, meta), caption)
        else:
            cid = self._api.create_reels_container(self._media_url(media, meta), caption)
        status = "IN_PROGRESS"
        for _ in range(self._poll_max):
            status = self._api.container_status(cid)
            if status in ("FINISHED", "ERROR", "EXPIRED"):
                break
            if self._dry_run:
                break
            time.sleep(self._poll_interval)
        if status == "EXPIRED":
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "контейнер IG истёк", action="создайте контейнер заново")
        if status == "ERROR":
            raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED, "контейнер IG в ERROR", action="проверьте public media URL и формат")
        mid = self._api.publish_container(cid)
        return PublishResult(external_id=mid, url=self._api.permalink(mid), state="published")

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
        video_url = self._media_url(media, meta)
        cid = self._api.create_reels_container(video_url, caption)
        # external_id temporarily = container; publisher should store external_sub_id=container
        return UploadResult(external_id=cid, url="", state="uploaded")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        raise NotSupported("schedule_publish")

    def list_remote(self, *, limit: int = 25) -> list[dict]:
        """Published-only (no stories/carousel MVP)."""
        return self._api.list_media(limit=limit)

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
            logger.warning("instagram list_remote failed: %s", type(exc).__name__)
            return RemotePage(items=[], partial=True, notes=[f"list_remote failed: {type(exc).__name__}"])
        items = []
        for it in raw or []:
            if not isinstance(it, dict):
                continue
            items.append(RemoteItem(
                platform="instagram",
                external_id=str(it.get("id") or it.get("external_id") or ""),
                title=str(it.get("title") or ""),
                status=str(it.get("status") or "published"),
                url=str(it.get("url") or it.get("link") or ""),
            ))
        return RemotePage(items=items, partial=True, notes=["via list_remote"])

def create_instagram_module(**deps: Any) -> InstagramModule:
    return InstagramModule(**deps)
