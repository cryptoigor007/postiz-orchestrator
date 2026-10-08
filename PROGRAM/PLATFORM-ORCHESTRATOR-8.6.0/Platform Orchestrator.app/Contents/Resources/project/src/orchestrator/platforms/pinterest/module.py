from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from ..base import AuthStatus,ModuleError,ModuleErrorCode,PlatformModule,PreparedMedia,MediaSpec,PublishMeta,PublishResult,PublishStatus
from ...http_client import ModuleHttpClient
from ..manifest import load_manifest
_MANIFEST=Path(__file__).with_name("manifest.yaml")
class PinterestModule(PlatformModule):
    def __init__(self,**deps:Any)->None:
        self.manifest=load_manifest(_MANIFEST)
        self.base=str(deps.get("base_url") or os.getenv("PINTEREST_API_BASE","https://api.pinterest.com/v5")).rstrip("/")
        self.token=str(deps.get("access_token") or os.getenv("PINTEREST_ACCESS_TOKEN",""))
        self.board_id=str(deps.get("board_id") or os.getenv("PINTEREST_BOARD_ID","")).strip()
        self._http=deps.get("http") or ModuleHttpClient(platform="pinterest",module_version=self.manifest.module_version)
    def _headers(self):return {"Authorization":f"Bearer {self.token}","Content-Type":"application/json"}
    def auth_status(self)->AuthStatus:
        if not self.token:return AuthStatus(False,account="pinterest",details="PINTEREST_ACCESS_TOKEN missing")
        r=self._http.request("GET",f"{self.base}/user_account",headers={"Authorization":f"Bearer {self.token}"})
        if r.status_code>=400:return AuthStatus(False,account="pinterest",details=f"user_account HTTP {r.status_code}")
        d=r.json() if r.content else {};return AuthStatus(True,account=str(d.get("username") or d.get("business_name") or "pinterest"),details="user_account ok")
    def validate_config(self,cfg:dict[str,Any])->list[str]:
        e=[]
        if not self.token:e.append("pinterest: PINTEREST_ACCESS_TOKEN required")
        if not self.board_id:e.append("pinterest: PINTEREST_BOARD_ID required")
        return e
    def prepare(self,media:MediaSpec)->PreparedMedia:return PreparedMedia(media.path,media.kind or "image")
    def upload_media(self, path: str, media_type: str = "image") -> str:
        p = Path(path)
        if not p.is_file():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"Pinterest: media file not found: {path}")
        init = self._http.request("POST", f"{self.base}/media", headers=self._headers(), json={"media_type": media_type}, idempotent=False)
        if init.status_code >= 400:
            raise ModuleError(ModuleErrorCode.TRANSIENT if init.status_code >= 500 else ModuleErrorCode.PLATFORM_REJECTED, f"Pinterest media init HTTP {init.status_code}", retryable=init.status_code >= 500)
        info = (init.json() if init.content else {})
        media_id = str(info.get("media_id") or "")
        upload_url = str(info.get("upload_url") or "")
        params = info.get("upload_parameters") or {}
        if not media_id or not upload_url:
            raise ModuleError(ModuleErrorCode.FATAL, "Pinterest: media init missing media_id/upload_url")
        content_type = "image/png" if p.suffix.lower() == ".png" else "image/jpeg" if media_type == "image" else "video/mp4"
        up_headers = {"Content-Type": content_type}
        up = self._http.request("POST", upload_url, headers=up_headers, params=params, data=p.read_bytes(), upload=True, idempotent=False)
        if up.status_code >= 400:
            raise ModuleError(ModuleErrorCode.TRANSIENT if up.status_code >= 500 else ModuleErrorCode.MEDIA_INVALID, f"Pinterest media upload HTTP {up.status_code}", retryable=up.status_code >= 500)
        return media_id

    def publish(self,media:PreparedMedia,meta:PublishMeta)->PublishResult:
        if not self.token or not self.board_id:raise ModuleError(ModuleErrorCode.AUTH_REQUIRED,"Pinterest: access token and board_id required")
        extra=meta.extra or {}; media_url=str(extra.get("media_url") or extra.get("image_url") or "").strip()
        video_id=str(extra.get("media_id") or "").strip()
        if not media_url and media.kind == "image" and media.path:
            media_id = self.upload_media(media.path, "image")
            media_url = str(extra.get("cover_image_url") or "").strip()
            if not media_url:
                raise ModuleError(ModuleErrorCode.MEDIA_INVALID,"Pinterest: cover_image_url is required after local image upload")
        title=str(meta.title or Path(media.path).stem or "Pin")[:100]
        description=str(meta.description or "")
        source = {"source_type":"video_id","media_id":video_id,"cover_image_url":str(extra.get("cover_image_url") or "")} if video_id else {"source_type":"image_url","url":media_url}
        payload={"board_id":self.board_id,"title":title,"description":description,"media_source":source}
        link=str(extra.get("link") or "").strip()
        if link:payload["link"]=link
        r=self._http.request("POST",f"{self.base}/pins",headers=self._headers(),json=payload,idempotent=False)
        if r.status_code>=400:
            code=ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.RATE_LIMIT if r.status_code==429 else ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code,f"Pinterest create Pin HTTP {r.status_code}",retryable=code in {ModuleErrorCode.RATE_LIMIT,ModuleErrorCode.TRANSIENT})
        d=r.json() if r.content else {};rid=str(d.get("id") or "")
        if not rid:raise ModuleError(ModuleErrorCode.FATAL,"Pinterest: Pin create without id")
        return PublishResult(external_id=rid,url=str(d.get("link") or ""),state="published")
    def get_status(self,external_id:str)->PublishStatus:
        r=self._http.request("GET",f"{self.base}/pins/{external_id}",headers={"Authorization":f"Bearer {self.token}"})
        if r.status_code==404:return PublishStatus(state="deleted")
        if r.status_code>=400:raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.FATAL,f"Pinterest get Pin HTTP {r.status_code}",retryable=r.status_code>=500)
        d=r.json() if r.content else {};return PublishStatus(state="published",url=str(d.get("link") or ""),raw=d)
    def delete(self,external_id:str)->bool:
        r=self._http.request("DELETE",f"{self.base}/pins/{external_id}",headers={"Authorization":f"Bearer {self.token}"},idempotent=True)
        if r.status_code==404:return True
        if r.status_code>=400:raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.FATAL,f"Pinterest delete Pin HTTP {r.status_code}",retryable=r.status_code>=500)
        return True

def create_module(**deps:Any)->PinterestModule:return PinterestModule(**deps)
