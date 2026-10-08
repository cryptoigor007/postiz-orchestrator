from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from ..base import AuthStatus, MediaSpec, ModuleError, ModuleErrorCode, PlatformModule, PreparedMedia, PublishMeta, PublishResult, PublishStatus
from ..manifest import load_manifest
from ...http_client import ModuleHttpClient

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class ListmonkModule(PlatformModule):
    """Native Listmonk campaign API adapter (newsletter publishing)."""

    def __init__(self, *, http=None, base_url: str = "", username: str = "", token: str = "", account_id: str = "", dry_run: bool = False, **_: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base_url = str(base_url or os.getenv("LISTMONK_BASE_URL", "")).rstrip("/")
        self.username = str(username or os.getenv("LISTMONK_API_USER", ""))
        self.token = str(token or os.getenv("LISTMONK_API_TOKEN", ""))
        self._account_id = str(account_id or os.getenv("LISTMONK_ACCOUNT_ID", ""))
        self._dry_run = bool(dry_run)
        self._http = http or ModuleHttpClient(platform="listmonk", module_version=self.manifest.module_version)

    def _headers(self) -> dict[str, str]:
        raw = f"{self.username}:{self.token}".encode()
        return {"Authorization": "Basic " + base64.b64encode(raw).decode(), "Content-Type": "application/json"}

    @staticmethod
    def _error(status_code: int, operation: str) -> ModuleError:
        if status_code in (401, 403):
            code = ModuleErrorCode.AUTH_EXPIRED
        elif status_code == 429:
            code = ModuleErrorCode.RATE_LIMIT
        elif status_code >= 500:
            code = ModuleErrorCode.TRANSIENT
        else:
            code = ModuleErrorCode.PLATFORM_REJECTED
        return ModuleError(code, f"Listmonk {operation} HTTP {status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(True, account=self._account_id or "listmonk", details="dry-run")
        if not self.base_url or not self.username or not self.token:
            return AuthStatus(False, account=self._account_id or self.base_url, details="LISTMONK_BASE_URL/LISTMONK_API_USER/LISTMONK_API_TOKEN missing")
        response = self._http.request("GET", f"{self.base_url}/api/lists", headers=self._headers(), params={"per_page": 1})
        if response.status_code >= 400:
            return AuthStatus(False, account=self._account_id or self.base_url, details=f"lists HTTP {response.status_code}")
        return AuthStatus(True, account=self._account_id or self.base_url, details="lists api ok")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        if self._dry_run:
            return []
        out: list[str] = []
        if not self.base_url:
            out.append("listmonk: LISTMONK_BASE_URL is required")
        if not self.username:
            out.append("listmonk: LISTMONK_API_USER is required")
        if not self.token:
            out.append("listmonk: LISTMONK_API_TOKEN is required")
        return out

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path, kind="text")

    def _lists(self, extra: dict[str, Any]) -> list[int]:
        values = extra.get("lists") or extra.get("list_ids") or os.getenv("LISTMONK_LIST_IDS", "")
        if isinstance(values, str):
            values = [x.strip() for x in values.split(",") if x.strip()]
        try:
            return [int(x) for x in (values or [])]
        except (TypeError, ValueError) as exc:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Listmonk: list ids must be integers") from exc

    def _campaign_payload(self, meta: PublishMeta) -> tuple[dict[str, Any], str]:
        extra = dict(meta.extra or {})
        lists = self._lists(extra)
        if not lists:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Listmonk: at least one list id is required")
        desired = str(extra.get("status") or ("scheduled" if extra.get("send_at") else "running"))
        payload = {
            "name": str(extra.get("name") or meta.title or "VideoMaker campaign"),
            "subject": str(extra.get("subject") or meta.title or "VideoMaker"),
            "lists": lists,
            "content_type": str(extra.get("content_type") or "richtext"),
            "messenger": str(extra.get("messenger") or "email"),
            "type": str(extra.get("type") or "regular"),
            "body": str(extra.get("body") or meta.description or ""),
        }
        for key in ("from_email", "altbody", "template_id", "tags", "send_at"):
            if extra.get(key) not in (None, ""):
                payload[key] = extra[key]
        return payload, desired

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if self._dry_run:
            return PublishResult(external_id="dry-listmonk", state="published")
        if self.validate_config({}):
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Listmonk: API credentials are missing")
        payload, desired = self._campaign_payload(meta)
        response = self._http.request("POST", f"{self.base_url}/api/campaigns", headers=self._headers(), json=payload, idempotent=False)
        if response.status_code >= 400:
            raise self._error(response.status_code, "create campaign")
        data = response.json().get("data") or {}
        campaign_id = str(data.get("id") or "")
        if not campaign_id:
            raise ModuleError(ModuleErrorCode.FATAL, "Listmonk: create campaign returned no id")
        current = str(data.get("status") or "draft")
        if desired != current:
            self._set_status(campaign_id, desired)
        return PublishResult(external_id=campaign_id, state="published" if desired == "running" else desired)

    def _set_status(self, external_id: str, status: str) -> None:
        response = self._http.request("PUT", f"{self.base_url}/api/campaigns/{external_id}/status", headers=self._headers(), json={"status": status}, idempotent=False)
        if response.status_code >= 400:
            raise self._error(response.status_code, f"set campaign status ({status})")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        if self._dry_run:
            return True
        extra = dict(patch.extra or {})
        payload: dict[str, Any] = {}
        if patch.title:
            payload["name"] = extra.get("name") or patch.title
            payload["subject"] = extra.get("subject") or patch.title
        if patch.description or extra.get("body") is not None:
            payload["body"] = extra.get("body") if extra.get("body") is not None else patch.description
        for key in ("lists", "content_type", "messenger", "type", "from_email", "altbody", "template_id", "tags", "send_at"):
            if key in extra:
                payload[key] = extra[key]
        if not payload:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Listmonk: no metadata fields supplied")
        response = self._http.request("PUT", f"{self.base_url}/api/campaigns/{external_id}", headers=self._headers(), json=payload, idempotent=False)
        if response.status_code >= 400:
            raise self._error(response.status_code, "update campaign")
        return True

    def get_status(self, external_id: str) -> PublishStatus:
        if self._dry_run:
            return PublishStatus(state="published")
        response = self._http.request("GET", f"{self.base_url}/api/campaigns/{external_id}", headers=self._headers())
        if response.status_code == 404:
            return PublishStatus(state="deleted")
        if response.status_code >= 400:
            raise self._error(response.status_code, "get campaign")
        data = response.json().get("data") or {}
        raw_status = str(data.get("status") or "draft").lower()
        state = {
            "running": "published",
            "finished": "published",
            "scheduled": "scheduled",
            "draft": "uploaded",
            "paused": "processing",
            "cancelled": "deleted",
        }.get(raw_status, raw_status)
        return PublishStatus(state=state, url=str(data.get("archive_url") or ""), raw=data)

    def delete(self, external_id: str) -> bool:
        if self._dry_run:
            return True
        response = self._http.request("DELETE", f"{self.base_url}/api/campaigns/{external_id}", headers=self._headers(), idempotent=True)
        if response.status_code == 404:
            return True
        if response.status_code >= 400:
            raise self._error(response.status_code, "delete campaign")
        return True


def create_module(**deps: Any) -> ListmonkModule:
    return ListmonkModule(**deps)
