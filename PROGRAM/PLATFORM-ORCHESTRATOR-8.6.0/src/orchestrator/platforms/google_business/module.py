from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..base import AuthStatus, MediaSpec, ModuleError, ModuleErrorCode, PlatformModule, PreparedMedia, PublishMeta, PublishResult, PublishStatus
from ..manifest import load_manifest
from ..messaging_http import resolve_token
from ...http_client import ModuleHttpClient

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class GoogleBusinessModule(PlatformModule):
    """Google Business Profile local-post adapter using the documented v4 localPosts resource."""

    def __init__(self, *, token_provider=None, http=None, account_id: str = "", location_id: str = "", dry_run: bool = False, **_: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self._token_provider = token_provider
        self._account_id = str(account_id or os.getenv("GOOGLE_BUSINESS_ACCOUNT_ID", "")).strip()
        self._location_id = str(location_id or os.getenv("GOOGLE_BUSINESS_LOCATION_ID", "")).strip()
        self._dry_run = bool(dry_run)
        self._http = http or ModuleHttpClient(platform="google_business", module_version=self.manifest.module_version)
        self._base = "https://mybusiness.googleapis.com/v4"

    def _token(self) -> str:
        return resolve_token(self._token_provider, "google_business", self._account_id)

    def _require(self) -> str:
        tok=self._token()
        if not tok: raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Google Business Profile: access token is required")
        if not self._account_id or not self._location_id: raise ModuleError(ModuleErrorCode.FATAL, "Google Business Profile: account_id and location_id are required")
        return tok

    def auth_status(self) -> AuthStatus:
        if self._dry_run: return AuthStatus(True, account=self._account_id or "google_business", details="dry-run")
        try:
            tok=self._require()
            r=self._http.request("GET", f"{self._base}/accounts/{self._account_id}/locations/{self._location_id}", headers={"Authorization":f"Bearer {tok}"})
            if r.status_code>=400:
                code=ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.RATE_LIMIT if r.status_code==429 else ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.FATAL
                raise ModuleError(code,f"Google Business location HTTP {r.status_code}",retryable=code in {ModuleErrorCode.RATE_LIMIT,ModuleErrorCode.TRANSIENT})
            d=r.json() if r.content else {}; return AuthStatus(True, account=str(d.get("title") or self._location_id), details="location ok")
        except ModuleError as exc:
            return AuthStatus(False, account=self._account_id or "google_business", details=exc.message)

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        out=[]
        if not self._account_id: out.append("google_business: GOOGLE_BUSINESS_ACCOUNT_ID is required")
        if not self._location_id: out.append("google_business: GOOGLE_BUSINESS_LOCATION_ID is required")
        if not self._token() and not self._dry_run: out.append("google_business: access token is required")
        return out

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path, kind="text")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if self._dry_run: return PublishResult(external_id="dry-google-business", state="published")
        tok=self._require(); extra=dict(meta.extra or {})
        payload={"languageCode": str(extra.get("languageCode") or "en-US"), "summary": str(extra.get("summary") or meta.description or meta.title or ""), "topicType": str(extra.get("topicType") or "STANDARD")}
        action=extra.get("callToAction")
        if isinstance(action, dict): payload["callToAction"]=action
        media_url=str(extra.get("media_url") or extra.get("sourceUrl") or "").strip()
        if media_url: payload["media"]= [{"mediaFormat":"PHOTO","sourceUrl":media_url}]
        r=self._http.request("POST", f"{self._base}/accounts/{self._account_id}/locations/{self._location_id}/localPosts", headers={"Authorization":f"Bearer {tok}"}, json=payload, idempotent=False)
        if r.status_code>=400:
            code=ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.RATE_LIMIT if r.status_code==429 else ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code,f"Google Business localPost HTTP {r.status_code}",retryable=code in {ModuleErrorCode.RATE_LIMIT,ModuleErrorCode.TRANSIENT})
        d=r.json() if r.content else {}; name=str(d.get("name") or d.get("localPostName") or "")
        if not name: raise ModuleError(ModuleErrorCode.FATAL,"Google Business localPost returned no resource name")
        return PublishResult(external_id=name,url=str(d.get("searchUrl") or d.get("url") or ""),state="published")

    def get_status(self, external_id: str) -> PublishStatus:
        if self._dry_run: return PublishStatus(state="published")
        tok=self._require(); r=self._http.request("GET", f"{self._base}/{str(external_id).lstrip('/')}", headers={"Authorization":f"Bearer {tok}"})
        if r.status_code==404: return PublishStatus(state="deleted")
        if r.status_code>=400: raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.FATAL,f"Google Business localPost HTTP {r.status_code}",retryable=r.status_code>=500)
        return PublishStatus(state="published", url=str((r.json() or {}).get("searchUrl") or ""), raw=r.json() if r.content else {})

    def delete(self, external_id: str) -> bool:
        if self._dry_run: return True
        tok=self._require(); r=self._http.request("DELETE", f"{self._base}/{str(external_id).lstrip('/')}", headers={"Authorization":f"Bearer {tok}"}, idempotent=True)
        if r.status_code==404: return True
        if r.status_code>=400: raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.FATAL,f"Google Business delete HTTP {r.status_code}",retryable=r.status_code>=500)
        return True


def create_module(**deps: Any) -> GoogleBusinessModule:
    return GoogleBusinessModule(**deps)
