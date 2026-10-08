from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..base import AuthStatus, MediaSpec, ModuleError, ModuleErrorCode, PlatformModule, PreparedMedia, PublishMeta, PublishResult
from ..manifest import load_manifest
from ...http_client import ModuleHttpClient

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class WhopModule(PlatformModule):
    """Whop App API feed-content adapter.

    The documented App API exposes feed content item creation. This module maps
    the supported create operation into the orchestration publish contract and
    intentionally does not invent edit/delete/status endpoints that are not
    part of the documented feed-content surface used here.
    """

    def __init__(self, *, api_key: str = "", user_id: str = "", experience_id: str = "", external_id_prefix: str = "orch", http=None, **_: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.api_key = str(api_key or os.getenv("WHOP_API_KEY", "")).strip()
        self.user_id = str(user_id or os.getenv("WHOP_USER_ID", "")).strip()
        self.experience_id = str(experience_id or os.getenv("WHOP_EXPERIENCE_ID", "")).strip()
        self.external_id_prefix = str(external_id_prefix or os.getenv("WHOP_EXTERNAL_ID_PREFIX", "orch")).strip()
        self._http = http or ModuleHttpClient(platform="whop", module_version=self.manifest.module_version)

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not self.api_key:
            errors.append("whop: WHOP_API_KEY is required")
        if not self.user_id:
            errors.append("whop: WHOP_USER_ID is required")
        if not self.experience_id:
            errors.append("whop: WHOP_EXPERIENCE_ID is required")
        return errors

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Whop: WHOP_API_KEY is required")
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    @staticmethod
    def _error(status: int, operation: str) -> ModuleError:
        if status in (401, 403):
            code = ModuleErrorCode.AUTH_EXPIRED
        elif status == 429:
            code = ModuleErrorCode.RATE_LIMIT
        elif status >= 500:
            code = ModuleErrorCode.TRANSIENT
        elif status in (400, 404):
            code = ModuleErrorCode.PLATFORM_REJECTED
        else:
            code = ModuleErrorCode.FATAL
        return ModuleError(code, f"Whop {operation} HTTP {status}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def auth_status(self) -> AuthStatus:
        if not self.api_key or not self.user_id or not self.experience_id:
            return AuthStatus(False, account=self.user_id or "whop", details="WHOP_API_KEY/USER_ID/EXPERIENCE_ID required")
        # Use the documented public identity endpoint to validate the bearer key path when a username is provided.
        username = str(os.getenv("WHOP_USERNAME", "")).strip()
        if not username:
            return AuthStatus(True, account=self.user_id, details="App API key configured; live identity probe requires WHOP_USERNAME")
        r = self._http.request("GET", f"https://api.whop.com/api/v1/users/{username}", headers=self._headers(), idempotent=True)
        if r.status_code >= 400:
            return AuthStatus(False, account=self.user_id, details=f"identity HTTP {r.status_code}")
        return AuthStatus(True, account=self.user_id, details="Whop identity ok")

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        kind = str(media.kind or "text").lower()
        if kind not in {"text", "image", "video"}:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"Whop: unsupported content kind {kind}")
        return PreparedMedia(path=media.path, kind=kind)

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if not self.user_id or not self.experience_id:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Whop: user_id and experience_id are required")
        body: dict[str, Any] = {
            "experience_id": self.experience_id,
            "user_id": self.user_id,
            "external_id": str((meta.extra or {}).get("external_id") or f"{self.external_id_prefix}-{abs(hash((meta.title, meta.description))) }"),
        }
        extra = dict(meta.extra or {})
        body["rest_path"] = str(extra.get("rest_path") or "")
        body["event_type"] = str(extra.get("event_type") or "social_orchestrator.publish")
        metadata = extra.get("metadata") or {}
        body["metadata"] = metadata if isinstance(metadata, dict) else {"metadata": str(metadata)}
        attachments = extra.get("file_attachments") or []
        if media.path and extra.get("file_url"):
            attachments = list(attachments) if isinstance(attachments, list) else [attachments]
            attachments.append({"type": "video" if media.kind == "video" else "image", "file_url": str(extra["file_url"])
            })
        if attachments:
            body["file_attachments"] = attachments
        if meta.title:
            body.setdefault("metadata", {})["title"] = meta.title
        if meta.description:
            body.setdefault("metadata", {})["description"] = meta.description

        r = self._http.request("POST", "https://api.whop.com/v5/app/feed_content_items", headers={**self._headers(), "Content-Type": "application/json"}, json=body, idempotent=False)
        if r.status_code >= 400:
            raise self._error(r.status_code, "feed_content_item create")
        data = r.json() if r.content else {}
        rid = str(data.get("id") or data.get("feed_content_item", {}).get("id") or body["external_id"])
        return PublishResult(external_id=rid, url=str(data.get("url") or ""), state="published")


def create_module(**deps: Any) -> WhopModule:
    return WhopModule(**deps)
