from __future__ import annotations
import hashlib, hmac, json, os
from pathlib import Path
from typing import Any
from ..messaging_http import NativeMessagingModule
from ..base import ModuleError, ModuleErrorCode

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class ViberModule(NativeMessagingModule):
    def __init__(self, **deps: Any) -> None:
        super().__init__(platform="viber", manifest_path=_MANIFEST, **deps)
        self.api_url = str(deps.get("api_url") or os.getenv("VIBER_API_URL", "https://chatapi.viber.com/pa")).rstrip("/")
        self._auth_token = str(deps.get("auth_token") or os.getenv("VIBER_AUTH_TOKEN", "")).strip()

    def _token(self) -> str:
        return self._auth_token or self._require_token()

    def auth_status(self):
        from ..base import AuthStatus
        try:
            tok = self._token()
        except ModuleError as exc:
            return AuthStatus(False, account=self._account_id or "viber", details=exc.message)
        r = self._http.request("POST", f"{self.api_url}/get_account_info", headers={"X-Viber-Auth-Token": tok}, json={}, idempotent=True)
        if r.status_code >= 400:
            return AuthStatus(False, account=self._account_id or "viber", details=f"HTTP {r.status_code}")
        d = r.json() if r.content else {}
        if int(d.get("status", 0) or 0) != 0:
            return AuthStatus(False, account=self._account_id or "viber", details=str(d.get("status_message") or "auth failed"))
        return AuthStatus(True, account=str(d.get("name") or self._account_id or "viber"), details="get_account_info ok")

    def send_message(self, recipient: str, message: dict[str, Any]) -> dict[str, Any]:
        receiver = str(recipient or message.get("receiver") or "").strip()
        if not receiver:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Viber: receiver is required")
        kind = str(message.get("type") or "text").lower()
        payload: dict[str, Any] = {"receiver": receiver, "type": kind, "min_api_version": 7}
        if kind == "text":
            text = str(message.get("text") or message.get("body") or "").strip()
            if not text:
                raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Viber: text is required")
            payload["text"] = text
        elif kind in {"picture", "video", "file", "url"}:
            payload.update({k: v for k, v in message.items() if k in {"media", "thumbnail", "text", "size", "file_name", "duration", "url"}})
            if kind in {"picture", "video"} and not payload.get("media"):
                raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"Viber: {kind} media is required")
            if kind == "url" and not payload.get("media") and not payload.get("url"):
                raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Viber: url is required")
        else:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"Viber: unsupported message type {kind}")
        sender = message.get("sender")
        if isinstance(sender, dict):
            payload["sender"] = sender
        r = self._http.request("POST", f"{self.api_url}/send_message", headers={"X-Viber-Auth-Token": self._token(), "Content-Type": "application/json"}, json=payload, idempotent=False)
        d = r.json() if r.content else {}
        if r.status_code >= 400 or int(d.get("status", 0) or 0) != 0:
            code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401, 403) else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code, f"Viber send failed: {d.get('status_message') or r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})
        return d

    def set_webhook(self, url: str, event_types: list[str] | None = None, *, send_name: bool | None = None, send_photo: bool | None = None) -> dict[str, Any]:
        if not url or not url.startswith("https://"):
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Viber webhook must use HTTPS")
        payload: dict[str, Any] = {"url": url}
        if event_types is not None:
            payload["event_types"] = event_types
        if send_name is not None:
            payload["send_name"] = bool(send_name)
        if send_photo is not None:
            payload["send_photo"] = bool(send_photo)
        r = self._http.request("POST", f"{self.api_url}/set_webhook", headers={"X-Viber-Auth-Token": self._token(), "Content-Type": "application/json"}, json=payload, idempotent=True)
        if r.status_code >= 400:
            raise ModuleError(ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL, f"Viber set_webhook HTTP {r.status_code}", retryable=r.status_code >= 500)
        d = r.json() if r.content else {}
        if int(d.get("status", 0) or 0) != 0:
            raise ModuleError(ModuleErrorCode.WEBHOOK_BROKEN, str(d.get("status_message") or "Viber set_webhook failed"))
        return d

    def broadcast_message(self, recipients: list[str], message: dict[str, Any]) -> dict[str, Any]:
        ids = [str(x).strip() for x in recipients if str(x).strip()]
        if not ids or len(ids) > 300:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Viber: broadcast recipients must contain 1..300 user ids")
        receiver_message = dict(message)
        receiver_message.pop("receiver", None)
        receiver_message["broadcast_list"] = ids
        kind = str(receiver_message.get("type") or "text").lower()
        if kind == "text" and not str(receiver_message.get("text") or receiver_message.get("body") or "").strip():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Viber: broadcast text is required")
        r = self._http.request("POST", f"{self.api_url}/broadcast_message", headers={"X-Viber-Auth-Token": self._token(), "Content-Type":"application/json"}, json=receiver_message, idempotent=False)
        d = r.json() if r.content else {}
        if r.status_code >= 400 or int(d.get("status", 0) or 0) != 0:
            code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code, f"Viber broadcast failed: {d.get('status_message') or r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT,ModuleErrorCode.TRANSIENT})
        return d

    def get_user_details(self, user_id: str) -> dict[str, Any]:
        uid = str(user_id or "").strip()
        if not uid:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Viber: user_id is required")
        r = self._http.request("POST", f"{self.api_url}/get_user_details", headers={"X-Viber-Auth-Token": self._token(), "Content-Type":"application/json"}, json={"id":uid}, idempotent=True)
        d = r.json() if r.content else {}
        if r.status_code >= 400 or int(d.get("status", 0) or 0) != 0:
            raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED, f"Viber get_user_details failed: {d.get('status_message') or r.status_code}")
        return d

    def remove_webhook(self) -> dict[str, Any]:
        return self.set_webhook("")

    def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool:
        sig = str(headers.get("X-Viber-Content-Signature") or "").strip().lower()
        if not sig:
            return False
        return hmac.compare_digest(sig, hmac.new(self._token().encode(), body, hashlib.sha256).hexdigest())

    def handle_webhook(self, headers: dict[str, str], body: bytes) -> dict[str, Any]:
        if not self.verify_webhook(headers, body):
            raise ModuleError(ModuleErrorCode.WEBHOOK_BROKEN, "Viber: invalid webhook signature")
        try:
            return json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise ModuleError(ModuleErrorCode.WEBHOOK_BROKEN, "Viber: invalid JSON webhook") from exc


def create_module(**deps: Any) -> ViberModule:
    return ViberModule(**deps)
