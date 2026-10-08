from __future__ import annotations
import os
from typing import Any
from urllib.parse import urlsplit
from pathlib import Path
from ..messaging_http import NativeMessagingModule
from ..base import ModuleError, ModuleErrorCode

_MANIFEST=Path(__file__).with_name("manifest.yaml")
_PREFIX="discord:"

class DiscordModule(NativeMessagingModule):
    def __init__(self, **deps: Any) -> None:
        super().__init__(platform="discord", manifest_path=_MANIFEST, **deps)
        self.webhook_url=str(deps.get("webhook_url") or os.getenv("DISCORD_WEBHOOK_URL", "")).strip()

    def _base_url(self, url: str|None=None) -> str:
        value=str(url or self.webhook_url).strip()
        if not value: raise ModuleError(ModuleErrorCode.AUTH_REQUIRED,"Discord: webhook URL required")
        return value.rstrip("/")

    def auth_status(self):
        from ..base import AuthStatus
        if not self.webhook_url:
            return AuthStatus(False,account=self._account_id or "discord",details="DISCORD_WEBHOOK_URL missing")
        r=self._http.request("GET",self.webhook_url)
        if r.status_code>=400:return AuthStatus(False,account=self._account_id or "discord",details=f"webhook HTTP {r.status_code}")
        d=r.json() if r.content else {}; return AuthStatus(True,account=str(d.get("name") or self._account_id or "discord"),details="webhook ok")

    def _payload(self, message: dict[str,Any]) -> dict[str,Any]:
        payload: dict[str,Any]={}
        text=str(message.get("text") or message.get("content") or message.get("body") or "").strip()
        if text: payload["content"]=text
        for k in ("username","avatar_url","embeds","allowed_mentions","components","flags","thread_name"):
            if k in message: payload[k]=message[k]
        if not payload: raise ModuleError(ModuleErrorCode.MEDIA_INVALID,"Discord: empty message")
        return payload

    def send_message(self, recipient: str, message: dict[str,Any]) -> dict[str,Any]:
        url=self._base_url(recipient or None)
        r=self._http.request("POST",url,params={"wait":"true"},json=self._payload(message),idempotent=False)
        if r.status_code>=400:
            code=ModuleErrorCode.RATE_LIMIT if r.status_code==429 else ModuleErrorCode.TRANSIENT if r.status_code>=500 else ModuleErrorCode.FATAL
            raise ModuleError(code,f"Discord webhook HTTP {r.status_code}",retryable=code in {ModuleErrorCode.RATE_LIMIT,ModuleErrorCode.TRANSIENT})
        data=r.json() if r.content else {"status":r.status_code,"ok":True}
        if isinstance(data,dict) and data.get("id"):
            data["external_id"]=f"{_PREFIX}{data['id']}"
        return data

    def update_message(self, external_id: str, message: dict[str,Any], *, webhook_url: str="") -> bool:
        mid=str(external_id or "").removeprefix(_PREFIX)
        if not mid.isdigit(): raise ModuleError(ModuleErrorCode.FATAL,f"Discord: bad external_id {external_id}")
        url=f"{self._base_url(webhook_url or None)}/messages/{mid}"
        r=self._http.request("PATCH",url,json=self._payload(message),idempotent=True)
        if r.status_code>=400:
            code=ModuleErrorCode.RATE_LIMIT if r.status_code==429 else ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.FATAL
            raise ModuleError(code,f"Discord edit HTTP {r.status_code}",retryable=code==ModuleErrorCode.RATE_LIMIT)
        return True

    def delete_message(self, external_id: str, *, webhook_url: str="") -> bool:
        mid=str(external_id or "").removeprefix(_PREFIX)
        if not mid.isdigit(): raise ModuleError(ModuleErrorCode.FATAL,f"Discord: bad external_id {external_id}")
        r=self._http.request("DELETE",f"{self._base_url(webhook_url or None)}/messages/{mid}",idempotent=True)
        if r.status_code in (200,202,204,404): return True
        if r.status_code==429: raise ModuleError(ModuleErrorCode.RATE_LIMIT,"Discord delete rate limited",retryable=True)
        raise ModuleError(ModuleErrorCode.FATAL,f"Discord delete HTTP {r.status_code}")

def create_module(**deps:Any)->DiscordModule:return DiscordModule(**deps)
