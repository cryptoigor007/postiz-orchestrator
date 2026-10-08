from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from ..messaging_http import NativeMessagingModule
from ..base import ModuleError, ModuleErrorCode
from ..manifest import load_manifest
_MANIFEST=Path(__file__).with_name("manifest.yaml")
class SlackModule(NativeMessagingModule):
    def __init__(self,**deps:Any)->None:
        super().__init__(platform="slack",manifest_path=_MANIFEST,**deps)
        self.api_url=str(deps.get("api_url") or os.getenv("SLACK_API_URL","https://slack.com/api")).rstrip("/")
        self.channel=str(deps.get("channel") or os.getenv("SLACK_CHANNEL_ID","")).strip()
    def _auth_headers(self): return {"Authorization":f"Bearer {self._require_token()}"}
    def auth_status(self):
        from ..base import AuthStatus
        try:
            headers = self._auth_headers()
        except ModuleError as exc:
            return AuthStatus(False, account=self._account_id or "slack", details=exc.message)
        r=self._http.request("POST",f"{self.api_url}/auth.test",headers=headers,idempotent=True)
        d=r.json() if r.content else {}
        if r.status_code>=400 or not d.get("ok"):
            return AuthStatus(False,account=self._account_id or "slack",details=str(d.get("error") or f"HTTP {r.status_code}"))
        return AuthStatus(True,account=str(d.get("team") or d.get("user") or self._account_id or "slack"),details="auth.test ok")
    def send_message(self,recipient:str,message:dict[str,Any])->dict[str,Any]:
        channel=str(recipient or message.get("channel") or self.channel).strip(); text=str(message.get("text") or message.get("body") or "").strip()
        if not channel or not text: raise ModuleError(ModuleErrorCode.MEDIA_INVALID,"Slack: channel and text are required")
        payload={"channel":channel,"text":text}
        for key in ("blocks","attachments","thread_ts","unfurl_links","unfurl_media"):
            if key in message: payload[key]=message[key]
        r=self._http.request("POST",f"{self.api_url}/chat.postMessage",headers={**self._auth_headers(),"Content-Type":"application/json"},json=payload,idempotent=False)
        return self._handle_api_result(r,"Slack chat.postMessage")

    def update_message(self, channel: str, ts: str, message: dict[str,Any]) -> dict[str,Any]:
        payload={"channel":str(channel),"ts":str(ts)}
        for key in ("text","blocks","attachments","markdown_text","metadata","parse","link_names"):
            if key in message: payload[key]=message[key]
        r=self._http.request("POST",f"{self.api_url}/chat.update",headers={**self._auth_headers(),"Content-Type":"application/json"},json=payload,idempotent=True)
        return self._handle_api_result(r,"Slack chat.update")

    def delete_message(self, channel: str, ts: str) -> dict[str,Any]:
        r=self._http.request("POST",f"{self.api_url}/chat.delete",headers={**self._auth_headers(),"Content-Type":"application/json"},json={"channel":str(channel),"ts":str(ts)},idempotent=True)
        return self._handle_api_result(r,"Slack chat.delete")

    def _handle_api_result(self, r: Any, action: str) -> dict[str,Any]:
        d=r.json() if r.content else {}
        err=str(d.get("error") or f"HTTP {r.status_code}") if isinstance(d,dict) else f"HTTP {r.status_code}"
        if r.status_code>=400 or (isinstance(d,dict) and not d.get("ok")):
            code=ModuleErrorCode.RATE_LIMIT if r.status_code==429 or err in {"ratelimited","rate_limited"} else ModuleErrorCode.AUTH_EXPIRED if err in {"invalid_auth","token_expired","token_revoked","not_authed"} or r.status_code in (401,403) else ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code,f"{action}: {err}",retryable=code in {ModuleErrorCode.RATE_LIMIT,ModuleErrorCode.TRANSIENT})
        return d if isinstance(d,dict) else {"data":d}

def create_module(**deps:Any)->SlackModule:return SlackModule(**deps)
