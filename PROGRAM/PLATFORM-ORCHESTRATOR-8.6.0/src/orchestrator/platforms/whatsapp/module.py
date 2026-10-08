from __future__ import annotations
import hashlib
import hmac
import mimetypes
import os
from pathlib import Path
from typing import Any
from ..messaging_http import NativeMessagingModule
from ..base import ModuleError, ModuleErrorCode

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class WhatsAppModule(NativeMessagingModule):
    """WhatsApp Cloud API messaging core (text/media/template).

    Production onboarding, business verification and template approval remain
    provider-side prerequisites; this module deliberately exposes only the API
    contract that can be exercised once credentials/assets exist.
    """

    def __init__(self, **deps: Any) -> None:
        super().__init__(platform="whatsapp", manifest_path=_MANIFEST, **deps)
        self.graph_version = str(deps.get("graph_version") or os.getenv("WHATSAPP_GRAPH_VERSION", "v26.0"))
        self.phone_number_id = str(deps.get("phone_number_id") or os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")).strip()
        self.base = str(
            deps.get("base_url")
            or os.getenv("META_GRAPH_BASE_URL", f"https://graph.facebook.com/{self.graph_version}")
        ).rstrip("/")

    def auth_status(self):
        from ..base import AuthStatus
        try:
            tok = self._require_token()
        except ModuleError as exc:
            return AuthStatus(False, account=self._account_id or "whatsapp", details=exc.message)
        if not self.phone_number_id:
            return AuthStatus(False, account=self._account_id or "whatsapp", details="WHATSAPP_PHONE_NUMBER_ID missing")
        r = self._http.request("GET", f"{self.base}/{self.phone_number_id}", headers={"Authorization": f"Bearer {tok}"})
        if r.status_code >= 400:
            return AuthStatus(False, account=self._account_id or self.phone_number_id, details=f"HTTP {r.status_code}")
        d = r.json() if r.content else {}
        return AuthStatus(True, account=str(d.get("display_phone_number") or d.get("verified_name") or self.phone_number_id), details="phone lookup ok")

    def _send(self, payload: dict[str, Any]) -> dict[str, Any]:
        tok = self._require_token()
        if not self.phone_number_id:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "WhatsApp: phone_number_id required")
        r = self._http.request(
            "POST", f"{self.base}/{self.phone_number_id}/messages",
            headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", **payload}, idempotent=False,
        )
        if r.status_code >= 400:
            code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401, 403) else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code, f"WhatsApp send HTTP {r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})
        return r.json() if r.content else {"status": r.status_code}

    def upload_media(self, path: str, *, mime_type: str | None = None) -> str:
        p = Path(path)
        if not p.is_file():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"WhatsApp: media not found: {path}")
        tok = self._require_token()
        mime = mime_type or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        with p.open("rb") as fh:
            r = self._http.request(
                "POST", f"{self.base}/{self.phone_number_id}/media",
                headers={"Authorization": f"Bearer {tok}"},
                data={"messaging_product":"whatsapp","type":mime},
                files={"file": (p.name, fh, mime)}, upload=True, idempotent=False,
            )
        if r.status_code >= 400:
            code = ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401,403) else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code, f"WhatsApp media upload HTTP {r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT,ModuleErrorCode.TRANSIENT})
        d = r.json() if r.content else {}
        mid = str(d.get("id") or "")
        if not mid:
            raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED, "WhatsApp media upload returned no id")
        return mid

    def mark_read(self, message_id: str) -> dict[str, Any]:
        mid = str(message_id or "").strip()
        if not mid:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WhatsApp: message_id is required")
        return self._send({"status":"read", "message_id":mid})

    def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool:
        signature = str(headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256") or "").strip()
        return self.verify_webhook_signature(os.getenv("META_APP_SECRET", ""), signature, body)

    @staticmethod
    def verify_webhook_signature(app_secret: str, signature: str, body: bytes) -> bool:
        secret = str(app_secret or "").encode()
        provided = str(signature or "").strip()
        if not secret or not provided.startswith("sha256="):
            return False
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(provided[7:], expected)

    def send_message(self, recipient: str, message: dict[str, Any]) -> dict[str, Any]:
        to = str(recipient or message.get("to") or "").strip()
        if not to:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WhatsApp: recipient is required")
        kind = str(message.get("type") or "text").lower()
        payload: dict[str, Any] = {"to": to, "type": kind}
        if kind == "text":
            text = str(message.get("text") or message.get("body") or "").strip()
            if not text:
                raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WhatsApp: text is required")
            payload["text"] = {"body": text, "preview_url": bool(message.get("preview_url", False))}
        elif kind in {"image", "video", "audio", "document", "sticker"}:
            media = dict(message.get(kind) or {})
            local_path = media.pop("path", None)
            if local_path and not media.get("id") and not media.get("link"):
                media["id"] = self.upload_media(str(local_path), mime_type=media.get("mime_type"))
                media.pop("mime_type", None)
            if not media.get("id") and not media.get("link"):
                raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"WhatsApp: {kind}.id or {kind}.link is required")
            payload[kind] = media
        elif kind == "template":
            template = message.get("template")
            if not isinstance(template, dict) or not template.get("name") or not (template.get("language") or {}).get("code"):
                raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WhatsApp: template name and language.code are required")
            payload["template"] = template
        elif kind == "interactive":
            interactive = message.get("interactive")
            if not isinstance(interactive, dict) or not interactive.get("type"):
                raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WhatsApp: interactive payload is required")
            payload["interactive"] = interactive
        else:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"WhatsApp: unsupported message type {kind}")
        return self._send(payload)


def create_module(**deps: Any) -> WhatsAppModule:
    return WhatsAppModule(**deps)
