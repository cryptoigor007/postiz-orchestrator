"""VK module — video.save + wall.post + promo (text+photo)."""
from __future__ import annotations

import logging

import os
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
    RemoteItem,
    RemotePage,
    UploadResult,
)
from ..manifest import load_manifest
from .api import VKApi

_MANIFEST = Path(__file__).with_name("manifest.yaml")


logger = logging.getLogger(__name__)

class VKModule(PlatformModule):
    def __init__(
        self,
        *,
        access_token: str = "",
        group_id: str = "",
        http: ModuleHttpClient | None = None,
        dry_run: bool = True,
        account_label: str = "",
        token_provider: Any = None,
        content_kind: str = "video_native",
        **_kw: Any,
    ) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self._dry_run = dry_run
        self._account_label = account_label or "vk"
        self._content_kind = content_kind or "video_native"
        tok = access_token or os.getenv("VK_ACCESS_TOKEN", "")
        gid = group_id or os.getenv("VK_GROUP_ID", "")
        if not tok and callable(token_provider):
            try:
                tok = token_provider("vk") or ""
            except Exception:
                tok = ""
        self._api = VKApi(tok, group_id=gid, http=http, dry_run=dry_run)
        self._group_id = gid

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_label, details="dry-run")
        if not self._api.token:
            return AuthStatus(ok=False, account=self._account_label, details="no token")
        return AuthStatus(ok=True, account=self._account_label, details="token present")

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        kind = media.kind or "video"
        notes: list[str] = []
        if self._content_kind in ("promo_text", "image_carousel"):
            kind = "image" if media.path else "text"
            notes.append(f"content_kind={self._content_kind}")
        return PreparedMedia(path=media.path or "", kind=kind, notes=notes)

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        title = meta.title or ""
        desc = meta.description or ""
        kind = self._content_kind
        if kind in ("promo_text", "image_carousel") or media.kind in ("image", "text"):
            message = f"{title}\n\n{desc}".strip()
            paths: list[str] = []
            if media.path and Path(media.path).is_file():
                paths.append(media.path)
            extra = getattr(meta, "extra_media", None) or getattr(meta, "media_paths", None)
            if isinstance(extra, (list, tuple)):
                for ep in extra:
                    if ep and Path(str(ep)).is_file() and str(ep) not in paths:
                        paths.append(str(ep))
            attachments: list[str] = []
            for pp in paths[:10]:
                try:
                    attachments.append(self._api.upload_wall_photo(pp))
                except Exception:
                    if not self._dry_run:
                        raise
            att = ",".join(attachments)
            when = getattr(meta, "scheduled_for", None)
            publish_date = None
            if when is not None:
                try:
                    publish_date = int(when.timestamp()) if hasattr(when, "timestamp") else int(when)
                except Exception:
                    publish_date = None
            resp = self._api.wall_post(
                message=message, attachments=att, publish_date=publish_date
            )
            pid = str(resp.get("post_id") or resp.get("id") or "0")
            owner = str(resp.get("owner_id") or (f"-{self._group_id}" if self._group_id else "0"))
            url = f"https://vk.com/wall{owner}_{pid}"
            state = "scheduled_platform" if publish_date else "published"
            return PublishResult(external_id=f"{owner}_{pid}", url=url, state=state)
        save = self._api.video_save(title=title, description=desc, wallpost=1)
        upload_url = str(save.get("upload_url") or "")
        if upload_url and media.path:
            try:
                up = self._api.upload_video_file(upload_url, media.path)
                if up.get("video_id"):
                    save["video_id"] = up.get("video_id")
                if up.get("owner_id"):
                    save["owner_id"] = up.get("owner_id")
            except Exception:
                if not self._dry_run:
                    raise
        vid = str(save.get("video_id") or save.get("vid") or "0")
        owner = str(save.get("owner_id") or (f"-{self._group_id}" if self._group_id else "0"))
        url = f"https://vk.com/video{owner}_{vid}"
        return PublishResult(external_id=f"{owner}_{vid}", url=url, state="published")

    def upload(
        self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None
    ) -> UploadResult:
        # early upload not primary; map to publish for video
        pr = self.publish(media, meta)
        return UploadResult(external_id=pr.external_id, url=pr.url, state="uploaded")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        # wall native publish_date requires create-time; for existing id — not supported cleanly
        raise NotSupported("schedule_publish")

    def delete(self, external_id: str) -> bool:
        parts = (external_id or "").split("_", 1)
        if len(parts) != 2:
            raise ModuleError(ModuleErrorCode.FATAL, f"bad external_id: {external_id}")
        owner, eid = parts
        try:
            return self._api.video_delete(owner, eid)
        except ModuleError:
            return self._api.wall_delete(owner, eid)

    def get_status(self, external_id: str) -> PublishStatus:
        if self._dry_run:
            return PublishStatus(state="published", url=f"https://vk.com/video{external_id}")
        parts=(external_id or "").split("_",1)
        if len(parts)!=2: return PublishStatus(state="failed",error="bad external_id")
        owner,eid=parts
        try:
            rows=self._api.video_get(f"{owner}_{eid}")
            if rows: return PublishStatus(state="published",url=f"https://vk.com/video{owner}_{eid}",raw=rows[0])
        except Exception as exc:
            logger.warning("VK video status lookup failed: %s", type(exc).__name__)
        try:
            rows=self._api.wall_get_by_id(f"{owner}_{eid}")
            if rows: return PublishStatus(state="published",url=f"https://vk.com/wall{owner}_{eid}",raw=rows[0])
        except Exception as exc:
            logger.warning("VK wall status lookup failed: %s", type(exc).__name__)
            return PublishStatus(state="unknown",error=f"status lookup failed: {type(exc).__name__}")
        return PublishStatus(state="unknown", error="VK status not found")

    def list_remote_items(
        self,
        *,
        kinds: set[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> RemotePage:
        if self._dry_run:
            return RemotePage(
                items=[
                    RemoteItem(
                        platform="vk",
                        external_id="dry_1",
                        title="dry",
                        status="published",
                        url="https://vk.com/video_dry",
                    )
                ]
            )
        return RemotePage(items=[], partial=True, notes=["list_remote partial"])

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        parts=(external_id or "").split("_",1)
        if len(parts)!=2: raise ModuleError(ModuleErrorCode.FATAL,f"bad external_id: {external_id}")
        owner,eid=parts
        message=f"{patch.title}\n\n{patch.description}".strip()
        return self._api.wall_edit(owner,eid,message=message)

    def publish_clip(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        """E8: Clips not enabled until VK clips API access for the app."""
        raise NotSupported("vk clips: capability clips=false until API access")


def create_vk_module(**deps: Any) -> VKModule:
    return VKModule(**deps)
