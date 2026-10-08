from __future__ import annotations
import os, hashlib, hmac
from pathlib import Path
from typing import Any
from ..messaging_http import NativeMessagingModule
from ..base import AuthStatus, ModuleError, ModuleErrorCode
_MANIFEST=Path(__file__).with_name("manifest.yaml")
class InstagramMessagingModule(NativeMessagingModule):
    def __init__(self, **deps: Any)->None:
        super().__init__(platform="instagram_messaging",manifest_path=_MANIFEST,**deps)
        self.ig_user_id=str(deps.get("ig_user_id") or os.getenv("INSTAGRAM_IG_USER_ID","")).strip()
        self.graph_version=os.getenv("META_GRAPH_VERSION","v26.0").strip()
        self.app_secret=str(deps.get("app_secret") or os.getenv("META_APP_SECRET","")).strip()
    def auth_status(self)->AuthStatus:
        try:
            token=self._require_token(); sender=self.ig_user_id or self._account_id
            if not sender: return AuthStatus(False,account="instagram_messaging",details="INSTAGRAM_IG_USER_ID missing")
            r=self._http.request("GET",f"https://graph.facebook.com/{self.graph_version}/{sender}",headers={"Authorization":f"Bearer {token}"},params={"fields":"id,username"},idempotent=True)
            if r.status_code>=400: return AuthStatus(False,account=sender,details=f"Graph HTTP {r.status_code}")
            d=r.json() if r.content else {}; return AuthStatus(True,account=str(d.get("username") or d.get("id") or sender),details="instagram identity ok")
        except ModuleError as e: return AuthStatus(False,account=self.ig_user_id or self._account_id,details=e.message)
    def send_message(self,recipient:str,message:dict[str,Any])->dict[str,Any]:
        token=self._require_token(); sender=self.ig_user_id or self._account_id
        if not sender: raise ModuleError(ModuleErrorCode.AUTH_REQUIRED,"Instagram Messaging: sender id is required")
        msg:dict[str,Any]={}
        text=str(message.get("text") or message.get("body") or "").strip()
        if text: msg["text"]=text
        if message.get("attachment"): msg["attachment"]=message["attachment"]
        if message.get("quick_replies"): msg["quick_replies"]=message["quick_replies"]
        if not msg: raise ModuleError(ModuleErrorCode.MEDIA_INVALID,"Instagram Messaging: empty message")
        body={"recipient":{"id":str(recipient).strip()},"message":msg}
        r=self._http.request("POST",f"https://graph.facebook.com/{self.graph_version}/{sender}/messages",headers={"Authorization":f"Bearer {token}"},json=body,idempotent=False)
        return self._json_or_error(r)
    def verify_webhook(self,headers:dict[str,str],body:bytes)->bool:
        signature=str(headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256") or "").strip()
        if not self.app_secret or not signature: return False
        raw=signature.split("=",1)[-1].strip(); digest=hmac.new(self.app_secret.encode(),body,hashlib.sha256).hexdigest()
        return hmac.compare_digest(raw,digest)
def create_module(**deps:Any)->InstagramMessagingModule:return InstagramMessagingModule(**deps)
