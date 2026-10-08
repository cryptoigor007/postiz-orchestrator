from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_messaging_auth_status_without_token_never_raises(monkeypatch):
    from orchestrator.platforms.line.module import LineModule
    from orchestrator.platforms.slack.module import SlackModule
    from orchestrator.platforms.viber.module import ViberModule
    from orchestrator.platforms.whatsapp.module import WhatsAppModule
    for env in [
        "LINE_ACCESS_TOKEN", "SLACK_ACCESS_TOKEN", "VIBER_ACCESS_TOKEN", "WHATSAPP_ACCESS_TOKEN",
        "LINE_CHANNEL_ACCESS_TOKEN", "VIBER_AUTH_TOKEN", "WHATSAPP_PHONE_NUMBER_ID",
    ]:
        monkeypatch.delenv(env, raising=False)
    mods = [LineModule(), SlackModule(), ViberModule(), WhatsAppModule()]
    for mod in mods:
        st = mod.auth_status()
        assert st.ok is False
        assert "token" in st.details.lower() or "access" in st.details.lower()


def test_status_sync_auth_failure_is_not_missing_on_platform():
    from orchestrator.platforms.base import ModuleError, ModuleErrorCode
    from orchestrator.status_sync import StatusSync, _StatusFetchFailure

    class Cfg:
        confirm_published_interval_sec = 300
        def engine_for(self, platform): return "module:fake"

    class Registry:
        def has(self, module_id): return True
        def create(self, *args, **kwargs):
            raise ModuleError(ModuleErrorCode.AUTH_EXPIRED, "token expired")

    obj = StatusSync.__new__(StatusSync)
    obj.cfg = Cfg()
    obj._module_registry = Registry()
    failure = obj._module_get_status("youtube", "ext", "acct")
    assert isinstance(failure, _StatusFetchFailure)
    assert failure.code == "AUTH_EXPIRED"


def test_reconciliation_no_longer_has_silent_past_due_pass():
    src = Path("src/orchestrator/reconciliation.py").read_text()
    assert "past_due update failed" in src
    assert "res.errors.append" in src


def test_webapp_request_id_support_is_present():
    server = Path("src/orchestrator/http_server.py").read_text()
    assert "X-Request-Id" in server
