from __future__ import annotations

import hashlib
import hmac
import json

from orchestrator.db import Database
from orchestrator.webhook_ingress import WebhookIngress


def test_viber_webhook_persists_and_deduplicates(tmp_path, monkeypatch):
    db = Database(tmp_path / "w.sqlite")
    monkeypatch.setenv("VIBER_ACCESS_TOKEN", "secret-token")
    ingress = WebhookIngress({"db": db, "module_registry": __import__("orchestrator.platforms", fromlist=["default_registry"]).default_registry(), "cfg": None})
    body = json.dumps({"event": "subscribed", "user_id": "u1", "message_token": 123}, separators=(",", ":")).encode()
    sig = hmac.new(b"secret-token", body, hashlib.sha256).hexdigest()
    headers = {"X-Viber-Content-Signature": sig}
    code, payload, _ = ingress.handle("POST", "/webhooks/viber", headers, body)
    assert code == 202 and payload["accepted"] is True
    code2, payload2, _ = ingress.handle("POST", "/webhooks/viber", headers, body)
    assert code2 == 202 and payload2["event_id"] == payload["event_id"]
    assert int(db.fetchone("SELECT COUNT(*) AS c FROM webhook_events WHERE provider='viber'")["c"]) == 1


def test_viber_bad_signature_rejected(tmp_path, monkeypatch):
    db = Database(tmp_path / "w2.sqlite")
    monkeypatch.setenv("VIBER_ACCESS_TOKEN", "secret-token")
    ingress = WebhookIngress({"db": db, "module_registry": __import__("orchestrator.platforms", fromlist=["default_registry"]).default_registry(), "cfg": None})
    code, payload, _ = ingress.handle("POST", "/webhooks/viber", {"X-Viber-Content-Signature": "bad"}, b'{"event":"message"}')
    assert code == 403 and "signature" in payload["error"]


def test_whatsapp_verification_challenge(tmp_path, monkeypatch):
    db = Database(tmp_path / "wa.sqlite")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
    ingress = WebhookIngress({"db": db, "module_registry": __import__("orchestrator.platforms", fromlist=["default_registry"]).default_registry(), "cfg": None})
    path = "/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=12345"
    code, payload, ctype = ingress.handle("GET", path, {}, b"")
    assert code == 200 and payload == "12345" and ctype.startswith("text/plain")
