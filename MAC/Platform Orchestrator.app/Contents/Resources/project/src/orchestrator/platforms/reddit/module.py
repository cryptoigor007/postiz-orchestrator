from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from ..base import AuthStatus,ModuleError,ModuleErrorCode,PlatformModule,PreparedMedia,MediaSpec,PublishMeta,PublishResult,PublishStatus
from ...http_client import ModuleHttpClient
from ..manifest import load_manifest
_MANIFEST=Path(__file__).with_name("manifest.yaml")
class RedditModule(PlatformModule):
    def __init__(self,**deps:Any)->None:
        self.manifest=load_manifest(_MANIFEST)
        self.base=str(deps.get("base_url") or os.getenv("REDDIT_API_BASE","https://oauth.reddit.com")).rstrip("/")
        self.token=str(deps.get("access_token") or os.getenv("REDDIT_ACCESS_TOKEN",""))
        self.subreddit=str(deps.get("subreddit") or os.getenv("REDDIT_SUBREDDIT","")).strip().lstrip("r/")
        self.ua=str(deps.get("user_agent") or os.getenv("REDDIT_USER_AGENT","platform-orchestrator/1.0"))
        self._http=deps.get("http") or ModuleHttpClient(platform="reddit",module_version=self.manifest.module_version)
    def _headers(self):return {"Authorization":f"Bearer {self.token}","User-Agent":self.ua}
    def auth_status(self)->AuthStatus:
        if not self.token:return AuthStatus(False,account="reddit",details="REDDIT_ACCESS_TOKEN missing")
        r=self._http.request("GET",f"{self.base}/api/v1/me",headers=self._headers())
        if r.status_code>=400:return AuthStatus(False,account="reddit",details=f"me HTTP {r.status_code}")
        d=r.json() if r.content else {};return AuthStatus(True,account=str(d.get("name") or "reddit"),details="me ok")
    def validate_config(self,cfg:dict[str,Any])->list[str]:
        e=[]
        if not self.token:e.append("reddit: REDDIT_ACCESS_TOKEN required")
        if not self.subreddit:e.append("reddit: REDDIT_SUBREDDIT required")
        return e
    def prepare(self,media:MediaSpec)->PreparedMedia:return PreparedMedia(media.path,"text")
    def publish(self,media:PreparedMedia,meta:PublishMeta)->PublishResult:
        if not self.token or not self.subreddit:raise ModuleError(ModuleErrorCode.AUTH_REQUIRED,"Reddit: access token and subreddit required")
        extra=meta.extra or {}; title=str(meta.title or Path(media.path).stem or "Post")[:300]
        kind="link" if extra.get("url") else "self"
        payload={"sr":self.subreddit,"title":title,"kind":kind,"api_type":"json","resubmit":"true"}
        if kind=="self":payload["text"]=str(extra.get("text") or meta.description or "")
        else:payload["url"]=str(extra.get("url") or "")
        r=self._http.request("POST",f"{self.base}/api/submit",headers={**self._headers(),"Content-Type":"application/x-www-form-urlencoded"},data=urlencode(payload).encode(),idempotent=False)
        if r.status_code>=400:
            code=ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.RATE_LIMIT if r.status_code==429 else ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code,f"Reddit submit HTTP {r.status_code}",retryable=code in {ModuleErrorCode.RATE_LIMIT,ModuleErrorCode.TRANSIENT})
        d=r.json() if r.content else {}; errs=((d.get("json") or {}).get("errors") or [])
        if errs:raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED,f"Reddit submit rejected: {errs[:1]}")
        data=(d.get("json") or {}).get("data") or {}; rid=str(data.get("name") or "")
        url=str(data.get("url") or "")
        if not rid:raise ModuleError(ModuleErrorCode.FATAL,"Reddit: submit without fullname/id")
        return PublishResult(external_id=rid,url=url,state="published")
    def get_status(self,external_id:str)->PublishStatus:
        r=self._http.request("GET",f"{self.base}/api/info",headers=self._headers(),params={"id":external_id})
        if r.status_code>=400:
            if r.status_code==404:return PublishStatus(state="deleted")
            raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.FATAL,f"Reddit get status HTTP {r.status_code}",retryable=r.status_code>=500)
        d=r.json() if r.content else {}; children=((((d.get("data") or {}).get("children") or [])))
        if not children:return PublishStatus(state="deleted")
        return PublishStatus(state="published",url=str(((children[0].get("data") or {}).get("url") or "")),raw=d)
    def delete(self,external_id:str)->bool:
        r=self._http.request("POST",f"{self.base}/api/del",headers={**self._headers(),"Content-Type":"application/x-www-form-urlencoded"},data=urlencode({"id":external_id}).encode(),idempotent=False)
        if r.status_code>=400:raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.FATAL,f"Reddit delete HTTP {r.status_code}",retryable=r.status_code>=500)
        return True

def create_module(**deps:Any)->RedditModule:return RedditModule(**deps)
