"""TikTok module — inbox v1: uploaded_inbox → waiting_manual_publish ≠ published."""
from __future__ import annotations

import logging

import json
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
from .api import TikTokApi

_MANIFEST = Path(__file__).with_name("manifest.yaml")


logger = logging.getLogger(__name__)

class TikTokModule(PlatformModule):
    def __init__(
        self,
        *,
        access_token: str = "",
        http: ModuleHttpClient | None = None,
        dry_run: bool = True,
        account_label: str = "",
        publish_mode: str = "inbox",
        token_provider: Any = None,
        **_kw: Any,
    ) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self._dry_run = dry_run
        self._account_label = account_label or "tiktok"
        self._publish_mode = publish_mode or "inbox"
        tok = access_token or os.getenv("TIKTOK_ACCESS_TOKEN", "")
        if not tok and callable(token_provider):
            try:
                tok = token_provider("tiktok") or ""
            except Exception:
                tok = ""
        self._api = TikTokApi(tok, http=http, dry_run=dry_run)
        self._inbox_store = Path(
            os.getenv("TIKTOK_INBOX_PATH")
            or str(Path(os.getenv("ORCH_DATA_DIR", "data")) / "tiktok_inbox.json")
        )
        self._inbox: dict[str, dict] = self._load_inbox()


    def _load_inbox(self) -> dict[str, dict]:
        try:
            if self._inbox_store.is_file():
                data = json.loads(self._inbox_store.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(k): (v if isinstance(v, dict) else {"state": str(v)}) for k, v in data.items()}
        except Exception as exc:
            logger.warning("tiktok inbox read failed: %s", type(exc).__name__)
        return {}

    def _save_inbox(self) -> None:
        try:
            self._inbox_store.parent.mkdir(parents=True, exist_ok=True)
            self._inbox_store.write_text(
                json.dumps(self._inbox, ensure_ascii=False, indent=0),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("tiktok inbox write failed: %s", type(exc).__name__)

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_label, details="dry-run")
        try:
            # creator_info only when direct/v2 enabled
            if os.getenv("TIKTOK_CREATOR_INFO", "").lower() in ("1", "true"):
                info = self._api.creator_info()
                return AuthStatus(ok=True, account=str(info.get("creator_username") or self._account_label))
            return AuthStatus(ok=True, account=self._account_label, details="token present")
        except ModuleError as e:
            return AuthStatus(ok=False, account=self._account_label, details=e.message)

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path or "", kind=media.kind or "video")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        """Inbox or direct; inbox ≠ published on public feed."""
        # ★★★ creator_info/query BEFORE Direct Post (TikTok requirement)
        if (self._publish_mode or "inbox") == "direct" and not self._dry_run:
            try:
                self._api.creator_info()
            except Exception:
                raise
        elif (self._publish_mode or "inbox") == "direct" and self._dry_run:
            self._api.creator_info()
        size=0
        if media.path and Path(media.path).is_file(): size=Path(media.path).stat().st_size
        if self._publish_mode == "direct" and not self._dry_run:
            if size <= 0: raise ModuleError(ModuleErrorCode.MEDIA_INVALID,"TikTok: direct post requires a local video file")
            chunk_size = size if size < 5 * 1024 * 1024 else 10 * 1024 * 1024
            total_chunks = 1 if size < 5 * 1024 * 1024 else (size + chunk_size - 1) // chunk_size
            init = self._api.init_upload(size, meta.title or "", privacy_level=str((meta.extra or {}).get("privacy_level") or "PUBLIC_TO_EVERYONE"), description=meta.description or "", chunk_size=chunk_size, total_chunk_count=total_chunks)
            self._api.upload_file(str(init["upload_url"]), media.path, chunk_size=chunk_size)
        else:
            init = self._api.init_upload(size or 1, meta.title or "", description=meta.description or "")
        pid = str(init.get("publish_id") or f"tt-inbox-{abs(hash(meta.title or 'x')) % 10**8}")
        state = "uploaded_inbox" if self._publish_mode == "inbox" else "published"
        self._inbox[pid] = {"title": meta.title, "state": state}
        self._save_inbox()
        # Honest: inbox ≠ published
        return PublishResult(external_id=pid, url="", state=state)

    def upload(self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None) -> UploadResult:
        pr = self.publish(media, meta)
        return UploadResult(external_id=pr.external_id, url="", state=pr.state or "uploaded_inbox")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        raise NotSupported("schedule_publish — TikTok inbox is manual/confirm")

    def get_status(self, external_id: str) -> PublishStatus:
        if external_id in self._inbox:
            st = self._inbox[external_id].get("state", "uploaded_inbox")
            if self._publish_mode == "direct" and not self._dry_run:
                try:
                    info=self._api.fetch_status(external_id); remote=str(info.get("status") or "").upper()
                    mapped={"PUBLISH_COMPLETE":"published","FAILED":"failed","PROCESSING_UPLOAD":"processing","PROCESSING_DOWNLOAD":"processing"}.get(remote,st)
                    return PublishStatus(state=mapped, raw=info, error=str(info.get("fail_reason") or ""))
                except ModuleError as e:
                    return PublishStatus(state=st,error=e.message)
            return PublishStatus(state=st)
        if self._dry_run: return PublishStatus(state="uploaded_inbox")
        return PublishStatus(state="unknown")

    def delete(self, external_id: str) -> bool:
        self._inbox.pop(external_id, None)
        self._save_inbox()
        return True

    def list_remote(self, *, limit: int = 25) -> list[dict]:
        """Public list only — inbox rows are NOT returned as published."""
        if self._dry_run:
            return []
        # public videos only when API allows
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
            logger.warning("tiktok list_remote failed: %s", type(exc).__name__)
            return RemotePage(items=[], partial=True, notes=[f"list_remote failed: {type(exc).__name__}"])
        items = []
        for it in raw or []:
            if not isinstance(it, dict):
                continue
            items.append(RemoteItem(
                platform="tiktok",
                external_id=str(it.get("id") or it.get("external_id") or ""),
                title=str(it.get("title") or ""),
                status=str(it.get("status") or "published"),
                url=str(it.get("url") or it.get("link") or ""),
            ))
        return RemotePage(items=items, partial=True, notes=["via list_remote"])

def create_tiktok_module(**deps: Any) -> TikTokModule:
    return TikTokModule(**deps)
