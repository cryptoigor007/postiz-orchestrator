"""Durable provider webhook ingress with signature/verification gates."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class WebhookIngress:
    def __init__(self, comps: dict[str, Any]):
        self.comps = comps
        self.db = comps["db"]
        self.registry = comps.get("module_registry")

    @staticmethod
    def _event_id(provider: str, headers: dict[str, str], body: bytes, payload: Any) -> str:
        for key in ("X-Event-Id", "X-Event-ID", "X-Request-Id", "X-Request-ID"):
            value = str(headers.get(key) or "").strip()
            if value:
                return value[:250]
        raw = body or json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256((provider + ":").encode() + raw).hexdigest()

    def _module(self, provider: str, account_id: str = "") -> Any | None:
        reg = self.registry
        if reg is None:
            return None
        try:
            from .auth_tokens import token_provider_for
            if reg.has(provider):
                return reg.create(
                    provider,
                    cfg=self.comps.get("cfg"),
                    dry_run=bool(self.comps.get("dry_run")),
                    token_provider=token_provider_for(provider),
                    account_id=account_id,
                    media_host=self.comps.get("media_host"),
                )
        except Exception:
            logger.debug("webhook module create failed: %s", provider, exc_info=True)
        return None

    def _verify(self, provider: str, path: str, headers: dict[str, str], body: bytes, payload: Any) -> tuple[bool, str | None]:
        provider = provider.lower()
        # Meta webhook verification challenge for WhatsApp/Graph based products.
        if provider in {"whatsapp", "facebook", "instagram", "threads", "messenger", "instagram_messaging"} and path.startswith("/webhooks/"):
            qs = parse_qs(urlparse(path).query)
            mode = (qs.get("hub.mode") or [""])[0]
            verify = (qs.get("hub.verify_token") or [""])[0]
            challenge = (qs.get("hub.challenge") or [""])[0]
            expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip() if provider == "whatsapp" else os.getenv("META_VERIFY_TOKEN", "").strip()
            if mode == "subscribe" and challenge and expected and verify == expected:
                return True, challenge
            if mode or verify or challenge:
                return False, None
        account_id = str(headers.get("X-Account-Id") or "").strip()
        mod = self._module(provider, account_id)
        verifier = getattr(mod, "verify_webhook", None) if mod is not None else None
        if verifier is not None:
            try:
                return bool(verifier(headers, body)), None
            except Exception:
                logger.warning("webhook verification failed for %s", provider, exc_info=True)
                return False, None
        # Never accept an unsigned webhook for a provider that declares webhooks but
        # has not implemented a verifier yet.
        return False, None

    def handle(self, method: str, request_path: str, headers: dict[str, str], body: bytes) -> tuple[int, Any, str]:
        parsed = urlparse(request_path)
        parts = [x for x in parsed.path.split("/") if x]
        if len(parts) < 2 or parts[0] != "webhooks":
            return 404, {"error": "not found"}, "application/json"
        provider = parts[1].lower()
        if method.upper() == "GET":
            ok, challenge = self._verify(provider, request_path, headers, body, None)
            if ok and challenge is not None:
                return 200, challenge, "text/plain; charset=utf-8"
            return 403, {"error": "webhook verification failed"}, "application/json"
        if method.upper() != "POST":
            return 405, {"error": "method not allowed"}, "application/json"
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return 400, {"error": "invalid json"}, "application/json"
        ok, _ = self._verify(provider, request_path, headers, body, payload)
        if not ok:
            return 403, {"error": "invalid webhook signature"}, "application/json"
        account_id = str(headers.get("X-Account-Id") or "").strip()
        event_id = self._event_id(provider, headers, body, payload)
        payload_hash = hashlib.sha256(body).hexdigest()
        try:
            self.db.execute(
                "INSERT INTO webhook_events(provider, account_id, event_id, payload_hash, signature_valid, received_at, payload_json) "
                "VALUES (?, ?, ?, ?, 1, datetime('now'), ?) "
                "ON CONFLICT(provider, account_id, event_id) DO NOTHING",
                (provider, account_id, event_id, payload_hash, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            )
        except Exception:
            logger.exception("webhook persistence failed for %s", provider)
            return 500, {"error": "webhook persistence failed"}, "application/json"
        return 202, {"accepted": True, "provider": provider, "event_id": event_id}, "application/json"
