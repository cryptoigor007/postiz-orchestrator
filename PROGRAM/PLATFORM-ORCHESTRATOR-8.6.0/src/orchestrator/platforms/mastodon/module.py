from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..base import MediaSpec, AuthStatus, ModuleError, ModuleErrorCode, PlatformModule, PreparedMedia, PublishMeta, PublishResult, PublishStatus
from ..manifest import load_manifest
from ..messaging_http import NativeMessagingModule

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class MastodonModule(NativeMessagingModule, PlatformModule):
    def __init__(self, **deps: Any) -> None:
        super().__init__(platform="mastodon", manifest_path=_MANIFEST, **deps)
        self.base_url = str(deps.get("base_url") or os.getenv("MASTODON_BASE_URL", "https://mastodon.social")).rstrip("/")

    def auth_status(self) -> AuthStatus:
        tok = self._require_token() if self._account_id or os.getenv("MASTODON_ACCESS_TOKEN") else ""
        if not tok:
            return AuthStatus(ok=False, account=self._account_id or "mastodon", details="access token missing")
        try:
            r = self._http.request("GET", f"{self.base_url}/api/v1/accounts/verify_credentials", headers={"Authorization": f"Bearer {tok}"})
            if r.status_code in (401,403):
                return AuthStatus(ok=False, account=self._account_id or "mastodon", details=f"HTTP {r.status_code}: token rejected")
            if r.status_code >= 400:
                raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL, f"Mastodon auth HTTP {r.status_code}", retryable=r.status_code >= 500)
            data = r.json() if r.content else {}
            return AuthStatus(ok=True, account=str(data.get("acct") or data.get("username") or self._account_id or "mastodon"), details="verify_credentials ok")
        except ModuleError:
            raise
        except Exception as exc:
            return AuthStatus(ok=False, account=self._account_id or "mastodon", details=f"auth failed: {type(exc).__name__}")

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        p = Path(media.path)
        if media.kind != "text" and not p.is_file():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"Mastodon: file not found: {media.path}")
        return PreparedMedia(path=str(p), kind=media.kind or "text")

    def _status_text(self, meta: PublishMeta) -> str:
        return str((meta.extra or {}).get("status") or meta.description or meta.title or "").strip()

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        tok = self._require_token()
        text = self._status_text(meta)
        if not text:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Mastodon: empty status", action="задайте текст/description")
        payload: dict[str, Any] = {"status": text}
        extra = meta.extra or {}
        visibility = str(extra.get("visibility") or "").strip()
        if visibility in {"public", "unlisted", "private", "direct"}:
            payload["visibility"] = visibility
        # Optional media upload. Mastodon accepts multipart /api/v2/media, then media_ids on status create.
        if media.kind in {"image", "video"} and media.path:
            p = Path(media.path)
            if p.is_file():
                with p.open("rb") as fh:
                    mr = self._http.request("POST", f"{self.base_url}/api/v2/media", headers={"Authorization": f"Bearer {tok}"}, files={"file": (p.name, fh, "application/octet-stream")}, idempotent=False, upload=True)
                if mr.status_code >= 400:
                    code = ModuleErrorCode.RATE_LIMIT if mr.status_code == 429 else (ModuleErrorCode.AUTH_EXPIRED if mr.status_code in (401,403) else ModuleErrorCode.MEDIA_INVALID if mr.status_code in (400,422) else ModuleErrorCode.TRANSIENT if mr.status_code >= 500 else ModuleErrorCode.FATAL)
                    raise ModuleError(code, f"Mastodon media upload HTTP {mr.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})
                md = mr.json() if mr.content else {}
                mid = str(md.get("id") or "")
                if mid:
                    payload["media_ids"] = [mid]
        r = self._http.request("POST", f"{self.base_url}/api/v1/statuses", headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, json=payload, idempotent=False)
        if r.status_code >= 400:
            code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else (ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.PLATFORM_REJECTED if r.status_code in (400,422) else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL)
            raise ModuleError(code, f"Mastodon status create HTTP {r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})
        data = r.json() if r.content else {}
        sid = str(data.get("id") or "")
        url = str(data.get("url") or "")
        if not sid:
            raise ModuleError(ModuleErrorCode.FATAL, "Mastodon: create status without id")
        return PublishResult(external_id=sid, url=url, state="published")

    def get_status(self, external_id: str) -> PublishStatus:
        tok = self._require_token()
        r = self._http.request("GET", f"{self.base_url}/api/v1/statuses/{external_id}", headers={"Authorization": f"Bearer {tok}"})
        if r.status_code == 404:
            return PublishStatus(state="deleted", raw={"http_status":404})
        if r.status_code in (401,403):
            raise ModuleError(ModuleErrorCode.AUTH_EXPIRED, f"Mastodon: status auth HTTP {r.status_code}")
        if r.status_code >= 500:
            raise ModuleError(ModuleErrorCode.TRANSIENT, f"Mastodon status HTTP {r.status_code}", retryable=True)
        if r.status_code >= 400:
            raise ModuleError(ModuleErrorCode.FATAL, f"Mastodon status HTTP {r.status_code}")
        data = r.json() if r.content else {}
        return PublishStatus(state="published", url=str(data.get("url") or ""), raw=data)

    def delete(self, external_id: str) -> bool:
        tok = self._require_token()
        r = self._http.request("DELETE", f"{self.base_url}/api/v1/statuses/{external_id}", headers={"Authorization": f"Bearer {tok}"}, idempotent=True)
        if r.status_code == 404:
            return True
        if r.status_code >= 400:
            raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL, f"Mastodon delete HTTP {r.status_code}", retryable=r.status_code >= 500)
        return True


def create_module(**deps: Any) -> MastodonModule:
    return MastodonModule(**deps)
