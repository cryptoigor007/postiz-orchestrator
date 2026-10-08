"""Facebook Page module — Reels (shorts) / Video (long), schedule, list partial."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ...http_client import ModuleHttpClient
from ..base import (
    AuthStatus, ClaimsResult, MediaSpec, ModuleError, ModuleErrorCode, NotSupported,
    PlatformModule, PreparedMedia, PublishMeta, PublishResult, PublishStatus, UploadResult,
)
from ..manifest import load_manifest
from .api import FacebookApi

_MANIFEST = Path(__file__).with_name("manifest.yaml")
logger = logging.getLogger(__name__)


class FacebookModule(PlatformModule):
    def __init__(
        self,
        *,
        page_token: str = "",
        page_id: str = "",
        http: ModuleHttpClient | None = None,
        dry_run: bool = True,
        account_label: str = "",
        media_host: Any = None,
        graph_version: str | None = None,
        token_provider: Any = None,
        cfg: Any = None,
        **_kw: Any,
    ) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self._dry_run = dry_run
        self._account_label = account_label or "facebook"
        self._media_host = media_host
        tok = page_token or os.getenv("FACEBOOK_PAGE_TOKEN", "")
        if not tok and callable(token_provider):
            try:
                tok = token_provider("facebook") or ""
            except Exception:
                tok = ""
        pid = page_id or os.getenv("FACEBOOK_PAGE_ID", "")
        ver = graph_version
        if not ver and cfg is not None:
            pcfg = (getattr(cfg, "platforms", {}) or {}).get("facebook")
            ver = getattr(pcfg, "graph_version", None) or os.getenv("META_GRAPH_VERSION") or "v26.0"
        if not ver:
            ver = os.getenv("META_GRAPH_VERSION") or "v26.0"
        if not pid and cfg is not None:
            pcfg = (getattr(cfg, "platforms", {}) or {}).get("facebook")
            pid = getattr(pcfg, "channel_id", "") or pid
        self._api = FacebookApi(tok, pid, http=http, dry_run=dry_run, graph_version=ver)

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_label, details="dry-run")
        try:
            info = self._api.page_info()
            return AuthStatus(ok=True, account=str(info.get("name") or self._account_label))
        except ModuleError as e:
            return AuthStatus(ok=False, account=self._account_label, details=e.message)

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path or "", kind=media.kind or "video")

    def _file_url(self, media: PreparedMedia, meta: PublishMeta) -> str:
        extra = meta.extra or {}
        if extra.get("video_url") or extra.get("file_url"):
            return str(extra.get("video_url") or extra.get("file_url"))
        if self._media_host and media.path:
            return str(self._media_host.upload(media.path, prefix="fb"))
        if self._dry_run:
            return "https://example.invalid/dry-fb.mp4"
        raise ModuleError(
            ModuleErrorCode.MEDIA_INVALID,
            "no public file_url / media_host for Facebook video",
            action="configure B2 or pass extra.video_url",
        )

    def _is_short(self, media: PreparedMedia, meta: PublishMeta) -> bool:
        extra = meta.extra or {}
        if extra.get("is_short") or extra.get("format") == "shorts":
            return True
        # heuristic: vertical / short path
        p = (media.path or "").lower()
        return "short" in p or "reel" in p

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        desc = " ".join(x for x in [meta.title or "", meta.description or ""] if x).strip()
        url = self._file_url(media, meta)
        if media.kind == "text" or not media.path:
            oid = self._api.feed_post(desc, link=str((meta.extra or {}).get("link") or ""))
            return PublishResult(external_id=oid, url=self._api.permalink(oid), state="published")
        if self._is_short(media, meta):
            res = self._api.reels_post(url, description=desc)
        else:
            res = self._api.video_post(url, description=desc, title=meta.title or "")
        oid = str(res.get("id") or "")
        return PublishResult(
            external_id=oid,
            url=str(res.get("permalink_url") or self._api.permalink(oid)),
            state="published",
        )

    def upload(self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None) -> UploadResult:
        desc = (meta.description or meta.title or "")[:5000]
        url = self._file_url(media, meta)
        ts = int(when.timestamp()) if when else None
        res = self._api.video_post(
            url, description=desc, title=meta.title or "",
            scheduled_publish_time=ts, published=when is None,
        )
        oid = str(res.get("id") or "")
        return UploadResult(external_id=oid, url="", state="scheduled" if when else "uploaded")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        # FB schedules at create time via scheduled_publish_time; cannot re-schedule arbitrary id easily
        if self._dry_run:
            return True
        raise NotSupported("schedule_publish on existing id — use upload(when=...)")

    def get_status(self, external_id: str) -> PublishStatus:
        if self._dry_run:
            return PublishStatus(state="published", url=f"https://www.facebook.com/{external_id}")
        try:
            d = self._api.get_video(external_id)
            raw_status = d.get("status")
            status_name = str((raw_status or {}).get("video_status") if isinstance(raw_status, dict) else raw_status or "").lower()
            if "processing" in status_name or "upload" in status_name:
                state = "processing"
            elif d.get("published") is False and d.get("scheduled_publish_time"):
                state = "scheduled"
            else:
                state = "published"
            return PublishStatus(state=state, url=str(d.get("permalink_url") or self._api.permalink(external_id)), raw=d)
        except ModuleError as e:
            return PublishStatus(state="failed", error=e.message)

    def delete(self, external_id: str) -> bool:
        return self._api.delete(external_id)

    def list_remote(self, *, limit: int = 25) -> list[dict[str, Any]]:
        """Partial list: published videos + scheduled posts."""
        out: list[dict[str, Any]] = []
        self._last_list_scheduled_error = ""
        for v in self._api.list_videos(limit=limit):
            out.append({
                "external_id": v.get("id"),
                "title": v.get("title"),
                "url": v.get("permalink_url"),
                "published_at": v.get("created_time"),
                "status": "published",
            })
        try:
            for s in self._api.list_scheduled_posts(limit=limit):
                out.append({
                    "external_id": s.get("id"),
                    "title": (s.get("message") or "")[:80],
                    "scheduled_for": s.get("scheduled_publish_time"),
                    "status": "scheduled",
                })
        except Exception:
            logger.exception("facebook scheduled inventory failed; returning partial result")
            self._last_list_scheduled_error = "scheduled inventory request failed"
        return out

    def check_claims(self, external_id: str) -> ClaimsResult:
        return ClaimsResult(supported=False)

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        desc = patch.description if patch.description else (patch.title or None)
        title = patch.title or None
        return self._api.update_video(external_id, description=desc, title=title)



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
            logger.warning("facebook list_remote failed: %s", type(exc).__name__)
            return RemotePage(items=[], partial=True, notes=[f"list_remote failed: {type(exc).__name__}"])
        items = []
        for it in raw or []:
            if not isinstance(it, dict):
                continue
            items.append(RemoteItem(
                platform="facebook",
                external_id=str(it.get("id") or it.get("external_id") or ""),
                title=str(it.get("title") or ""),
                status=str(it.get("status") or "published"),
                url=str(it.get("url") or it.get("link") or ""),
            ))
        notes = ["via list_remote"]
        if getattr(self, "_last_list_scheduled_error", ""):
            notes.append(str(self._last_list_scheduled_error))
        return RemotePage(items=items, partial=True, notes=notes)

def create_facebook_module(**deps: Any) -> FacebookModule:
    return FacebookModule(**deps)
