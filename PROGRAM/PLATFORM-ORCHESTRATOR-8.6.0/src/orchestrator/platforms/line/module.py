from __future__ import annotations
import base64, hashlib, hmac, os
from pathlib import Path
from typing import Any
from ..messaging_http import NativeMessagingModule
from ..base import ModuleError, ModuleErrorCode

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class LineModule(NativeMessagingModule):
    def __init__(self, **deps: Any) -> None:
        super().__init__(platform="line", manifest_path=_MANIFEST, **deps)
        self.api_url = str(deps.get("api_url") or os.getenv("LINE_API_URL", "https://api.line.me/v2/bot")).rstrip("/")
        self.channel_secret = str(deps.get("channel_secret") or os.getenv("LINE_CHANNEL_SECRET", "")).strip()

    def auth_status(self):
        from ..base import AuthStatus
        try:
            tok = self._require_token()
        except ModuleError as exc:
            return AuthStatus(False, account=self._account_id or "line", details=exc.message)
        r = self._http.request("GET", f"{self.api_url}/info", headers={"Authorization": f"Bearer {tok}"})
        if r.status_code >= 400:
            return AuthStatus(False, account=self._account_id or "line", details=f"HTTP {r.status_code}")
        d = r.json() if r.content else {}
        return AuthStatus(True, account=str(d.get("displayName") or self._account_id or "line"), details="bot info ok")

    def send_message(self, recipient: str, message: dict[str, Any]) -> dict[str, Any]:
        to = str(recipient or message.get("to") or "").strip()
        if not to:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "LINE: recipient is required")
        msg_type = str(message.get("type") or "text").lower()
        msg = self._message_object(message)
        r = self._http.request("POST", f"{self.api_url}/message/push", headers={"Authorization": f"Bearer {self._require_token()}", "Content-Type": "application/json"}, json={"to": to, "messages": [msg]}, idempotent=False)
        if r.status_code >= 400:
            code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401, 403) else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code, f"LINE push HTTP {r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})
        return r.json() if r.content else {"status": r.status_code}

    def verify_webhook(self, headers: dict[str, str] | str, body: bytes) -> bool:
        signature = (str(headers).strip() if isinstance(headers, str) else str(headers.get("X-Line-Signature") or headers.get("x-line-signature") or "").strip())
        if not self.channel_secret or not signature:
            return False
        digest = base64.b64encode(hmac.new(self.channel_secret.encode(), body, hashlib.sha256).digest()).decode()
        return hmac.compare_digest(digest, signature)


    def send_multicast(self, recipients: list[str], message: dict[str,Any]) -> dict[str,Any]:
        tos=[str(x).strip() for x in recipients if str(x).strip()]
        if not tos: raise ModuleError(ModuleErrorCode.MEDIA_INVALID,"LINE: recipients are required")
        r=self._http.request("POST",f"{self.api_url}/message/multicast",headers={"Authorization":f"Bearer {self._require_token()}","Content-Type":"application/json"},json={"to":tos,"messages":[self._message_object(message)]},idempotent=False)
        return self._json_or_error(r)

    def validate_push(self, message: dict[str,Any]) -> dict[str,Any]:
        r=self._http.request("POST",f"{self.api_url}/message/validate/push",headers={"Authorization":f"Bearer {self._require_token()}","Content-Type":"application/json"},json={"to":"U_VALIDATE","messages":[self._message_object(message)]},idempotent=True)
        return self._json_or_error(r)

    def get_webhook_endpoint(self) -> dict[str,Any]:
        r=self._http.request("GET",f"{self.api_url}/channel/webhook/endpoint",headers={"Authorization":f"Bearer {self._require_token()}"},idempotent=True)
        return self._json_or_error(r)

    def set_webhook_endpoint(self, endpoint: str) -> dict[str,Any]:
        if not str(endpoint).startswith("https://"):
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID,"LINE: webhook endpoint must use HTTPS")
        r=self._http.request("PUT",f"{self.api_url}/channel/webhook/endpoint",headers={"Authorization":f"Bearer {self._require_token()}","Content-Type":"application/json"},json={"endpoint":str(endpoint)},idempotent=True)
        return self._json_or_error(r)

    def _message_object(self, message: dict[str,Any]) -> dict[str,Any]:
        return self._build_message(message)

    def _build_message(self, message: dict[str,Any]) -> dict[str,Any]:
        msg_type=str(message.get("type") or "text").lower()
        if msg_type=="text":
            text=str(message.get("text") or message.get("body") or "").strip()
            if not text: raise ModuleError(ModuleErrorCode.MEDIA_INVALID,"LINE: text is required")
            out={"type":"text","text":text}
            for k in ("quickReply","quoteToken"):
                if k in message: out[k]=message[k]
            return out
        if msg_type in {"image","video","audio"}:
            allowed={"type","originalContentUrl","previewImageUrl","duration"}
            return {k:v for k,v in message.items() if k in allowed and v is not None}
        msg=dict(message.get("message") or {})
        if not msg.get("type"): raise ModuleError(ModuleErrorCode.MEDIA_INVALID,f"LINE: unsupported message type {msg_type}")
        return msg

def create_module(**deps: Any) -> LineModule:
    return LineModule(**deps)
