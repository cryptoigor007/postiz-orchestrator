"""X (Twitter) module — text + up to 4 images; orchestrator schedule."""
from __future__ import annotations

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
    RemotePage,
    UploadResult,
)
from ..manifest import load_manifest
from .api import XApi

_MANIFEST = Path(__file__).with_name("manifest.yaml")
MAX_CHARS = 280


class XModule(PlatformModule):
    def __init__(
        self,
        *,
        access_token: str = "",
        http: ModuleHttpClient | None = None,
        dry_run: bool = True,
        account_label: str = "",
        token_provider: Any = None,
        max_chars: int = MAX_CHARS,
        **_kw: Any,
    ) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self._dry_run = dry_run
        self._account_label = account_label or "x"
        self._max_chars = int(max_chars or MAX_CHARS)
        self._max_images = 4
        tok = access_token or os.getenv("X_ACCESS_TOKEN", "")
        if not tok and callable(token_provider):
            try:
                tok = token_provider("x") or ""
            except Exception:
                tok = ""
        self._api = XApi(tok, http=http, dry_run=dry_run)

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_label, details="dry-run")
        if not self._api.token:
            return AuthStatus(ok=False, account=self._account_label, details="no token")
        return AuthStatus(ok=True, account=self._account_label, details="token present")

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path or "", kind=media.kind or "text")

    def _compose_text(self, meta: PublishMeta) -> str:
        parts = [meta.title or "", meta.description or "", meta.hashtags or ""]
        text = "\n".join(p for p in parts if p).strip()
        if len(text) > self._max_chars:
            text = text[: self._max_chars - 1].rstrip() + "…"
        return text

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        text = self._compose_text(meta)
        paths: list[str] = []
        if media.path and Path(media.path).is_file():
            paths.append(media.path)
        extra = getattr(meta, "extra_media", None) or getattr(meta, "media_paths", None)
        if isinstance(extra, (list, tuple)):
            for ep in extra:
                if ep and Path(str(ep)).is_file() and str(ep) not in paths:
                    paths.append(str(ep))
        # X allows up to 4 images. Video uses one chunked media upload.
        media_ids: list[str] = []
        for pp in paths[: self._max_images]:
            if media.kind not in ("image", "video", "text", "") and media.kind:
                # still try image upload for promo frames
                pass
            try:
                media_type = "video/mp4" if media.kind == "video" or Path(pp).suffix.lower() in {".mp4", ".mov", ".m4v"} else "image/jpeg"
                mid = self._api.upload_media(pp, media_type=media_type)
                if mid:
                    media_ids.append(mid)
            except ModuleError:
                if not self._dry_run:
                    raise
        resp = self._api.create_tweet(text, media_ids=media_ids or None)
        tid = str(resp.get("id") or "0")
        return PublishResult(
            external_id=tid,
            url=f"https://x.com/i/status/{tid}",
            state="published",
        )

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        raise NotSupported("schedule_publish")

    def delete(self, external_id: str) -> bool:
        return self._api.delete_tweet(external_id)

    def get_status(self, external_id: str) -> PublishStatus:
        if self._dry_run:
            return PublishStatus(state="published", url=f"https://x.com/i/status/{external_id}")
        try:
            data = self._api.get_tweet(external_id)
            return PublishStatus(state="published", url=f"https://x.com/i/status/{data.get("id") or external_id}")
        except ModuleError as exc:
            if exc.code == ModuleErrorCode.AUTH_REQUIRED:
                raise
            return PublishStatus(state="unknown", url=f"https://x.com/i/status/{external_id}", error=str(exc))

    def list_remote_items(
        self,
        *,
        kinds: set[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> RemotePage:
        return RemotePage(
            items=[],
            partial=True,
            notes=["remote inventory unavailable on current X tier; empty items are not authoritative"],
        )

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        raise NotSupported("update_metadata")


def create_x_module(**deps: Any) -> XModule:
    return XModule(**deps)
