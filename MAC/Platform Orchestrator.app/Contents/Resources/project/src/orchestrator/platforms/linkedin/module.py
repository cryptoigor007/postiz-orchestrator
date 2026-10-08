from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import quote
from typing import Any
from ..base import AuthStatus,ModuleError,ModuleErrorCode,PlatformModule,PreparedMedia,MediaSpec,PublishMeta,PublishResult,PublishStatus
from ...http_client import ModuleHttpClient
from ..manifest import load_manifest
_MANIFEST=Path(__file__).with_name("manifest.yaml")
class LinkedInModule(PlatformModule):
    def __init__(self,**deps:Any)->None:
        self.manifest=load_manifest(_MANIFEST)
        self.base=str(deps.get("base_url") or os.getenv("LINKEDIN_API_BASE","https://api.linkedin.com")).rstrip("/")
        self.token=str(deps.get("access_token") or os.getenv("LINKEDIN_ACCESS_TOKEN",""))
        self.author=str(deps.get("author_urn") or os.getenv("LINKEDIN_AUTHOR_URN",""))
        self.version=str(deps.get("api_version") or os.getenv("LINKEDIN_API_VERSION","202604"))
        self._http=deps.get("http") or ModuleHttpClient(platform="linkedin",module_version=self.manifest.module_version)
    def _headers(self)->dict[str,str]: return {"Authorization":f"Bearer {self.token}","Content-Type":"application/json","LinkedIn-Version":self.version,"X-Restli-Protocol-Version":"2.0.0"}
    def auth_status(self)->AuthStatus:
        if not self.token:return AuthStatus(False,account=self.author or "linkedin",details="LINKEDIN_ACCESS_TOKEN missing")
        r=self._http.request("GET",f"{self.base}/v2/userinfo",headers={"Authorization":f"Bearer {self.token}","LinkedIn-Version":self.version})
        if r.status_code>=400:return AuthStatus(False,account=self.author or "linkedin",details=f"userinfo HTTP {r.status_code}")
        d=r.json() if r.content else {}; return AuthStatus(True,account=str(d.get("name") or d.get("sub") or self.author or "linkedin"),scopes=[],details="userinfo ok")
    def validate_config(self,cfg:dict[str,Any])->list[str]:
        e=[]
        if not self.token:e.append("linkedin: LINKEDIN_ACCESS_TOKEN required")
        if not self.author:e.append("linkedin: LINKEDIN_AUTHOR_URN required")
        return e
    def prepare(self,media:MediaSpec)->PreparedMedia:
        if media.kind!="text" and not Path(media.path).is_file():raise ModuleError(ModuleErrorCode.MEDIA_INVALID,f"LinkedIn: file not found: {media.path}")
        return PreparedMedia(path=media.path,kind=media.kind or "text")
    def upload_image(self, path: str) -> str:
        p = Path(path)
        if not p.is_file():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"LinkedIn: image file not found: {path}")
        owner = self.author
        init_url = f"{self.base}/rest/images?action=initializeUpload"
        r = self._http.request("POST", init_url, headers=self._headers(), json={"initializeUploadRequest": {"owner": owner}}, idempotent=False)
        if r.status_code >= 400:
            raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.PLATFORM_REJECTED, f"LinkedIn image initialize HTTP {r.status_code}", retryable=r.status_code >= 500)
        value = (r.json() if r.content else {}).get("value") or {}
        upload_url, image = str(value.get("uploadUrl") or ""), str(value.get("image") or "")
        if not upload_url or not image:
            raise ModuleError(ModuleErrorCode.FATAL, "LinkedIn: image initialize response missing uploadUrl/image")
        content_type = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        up = self._http.request("PUT", upload_url, headers={"Content-Type": content_type}, data=p.read_bytes(), upload=True, idempotent=True)
        if up.status_code >= 400:
            raise ModuleError(ModuleErrorCode.TRANSIENT if up.status_code >= 500 else ModuleErrorCode.MEDIA_INVALID, f"LinkedIn image upload HTTP {up.status_code}", retryable=up.status_code >= 500)
        return image

    def publish(self,media:PreparedMedia,meta:PublishMeta)->PublishResult:
        if not self.token or not self.author:raise ModuleError(ModuleErrorCode.AUTH_REQUIRED,"LinkedIn: access token and author URN required")
        commentary=str((meta.extra or {}).get("commentary") or meta.description or meta.title or "")
        payload={"author":self.author,"commentary":commentary,"visibility":"PUBLIC","distribution":{"feedDistribution":"MAIN_FEED","targetEntities":[],"thirdPartyDistributionChannels":[]},"lifecycleState":"PUBLISHED","isReshareDisabledByAuthor":False}
        # The REST Posts API supports text natively. Media upload is intentionally not inferred from a local file.
        media_urn=str((meta.extra or {}).get("media_urn") or "").strip()
        if not media_urn and media.kind == "image" and media.path:
            media_urn = self.upload_image(media.path)
        if media_urn:
            payload["content"]={"media":{"id":media_urn}}
        r=self._http.request("POST",f"{self.base}/rest/posts",headers=self._headers(),json=payload,idempotent=False)
        if r.status_code>=400:
            code=ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.RATE_LIMIT if r.status_code==429 else ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code,f"LinkedIn post HTTP {r.status_code}",retryable=code in {ModuleErrorCode.RATE_LIMIT,ModuleErrorCode.TRANSIENT})
        rid=str(r.headers.get("x-restli-id") or r.headers.get("location") or "")
        if not rid and r.content:
            try: rid=str((r.json() or {}).get("id") or "")
            except Exception as exc:
                logger.debug("LinkedIn response id parse failed: %s", type(exc).__name__)
        if not rid:raise ModuleError(ModuleErrorCode.FATAL,"LinkedIn: post create without remote id")
        return PublishResult(external_id=rid,url="",state="published")
    def get_status(self,external_id:str)->PublishStatus:
        # REST Posts GET by encoded URN. LinkedIn response is authoritative for existence.
        encoded = quote(str(external_id), safe="")
        r=self._http.request("GET",f"{self.base}/rest/posts/{encoded}",headers=self._headers(),params={"viewContext":"AUTHOR"})
        if r.status_code==404:return PublishStatus(state="deleted")
        if r.status_code>=400:raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.FATAL,f"LinkedIn get post HTTP {r.status_code}",retryable=r.status_code>=500)
        d=r.json() if r.content else {}; return PublishStatus(state="published",raw=d)
    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        fields: dict[str, Any] = {}
        commentary = " ".join(x for x in [patch.title or "", patch.description or "", patch.hashtags or ""] if x).strip()
        if commentary:
            fields["commentary"] = commentary
        extra = patch.extra or {}
        if extra.get("content_call_to_action_label"):
            fields["contentCallToActionLabel"] = str(extra["content_call_to_action_label"])
        if extra.get("content_landing_page"):
            fields["contentLandingPage"] = str(extra["content_landing_page"])
        if not fields:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "LinkedIn: update_metadata requires commentary or supported CTA fields")
        encoded = quote(str(external_id), safe="")
        r=self._http.request(
            "POST", f"{self.base}/rest/posts/{encoded}", headers={**self._headers(), "X-RestLi-Method":"PARTIAL_UPDATE"},
            json={"patch":{"$set":fields}}, idempotent=False,
        )
        if r.status_code >= 400:
            code=ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.RATE_LIMIT if r.status_code==429 else ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code,f"LinkedIn update HTTP {r.status_code}",retryable=code in {ModuleErrorCode.RATE_LIMIT,ModuleErrorCode.TRANSIENT})
        return True

    def delete(self,external_id:str)->bool:
        encoded = quote(str(external_id), safe="")
        r=self._http.request("DELETE",f"{self.base}/rest/posts/{encoded}",headers={**self._headers(), "X-RestLi-Method":"DELETE"},idempotent=True)
        if r.status_code==404:return True
        if r.status_code>=400:raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.FATAL,f"LinkedIn delete HTTP {r.status_code}",retryable=r.status_code>=500)
        return True


logger = logging.getLogger(__name__)
def create_module(**deps:Any)->LinkedInModule:return LinkedInModule(**deps)
