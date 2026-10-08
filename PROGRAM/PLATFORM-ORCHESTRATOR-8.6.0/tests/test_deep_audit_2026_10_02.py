from __future__ import annotations

import httpx
import time
import json
import datetime

from orchestrator.claims import run_claims_check
from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.http_client import ModuleHttpClient
from orchestrator.platforms.token_store import make_meta_token_store
from orchestrator.telegram_bot import TelegramNotifier, setup_commands
from orchestrator.token_lifecycle import TokenLifecycleStore


def test_meta_refresh_uses_access_token_as_fb_exchange_token(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.content.decode())
        return httpx.Response(200, json={"access_token": "NEW", "expires_in": 3600})

    http = ModuleHttpClient(
        platform="instagram",
        module_version="audit",
        transport=httpx.MockTransport(handler),
        max_retries=1,
    )
    store = make_meta_token_store(
        "instagram",
        tokens_path=tmp_path / "ig.json",
        client_id="CID",
        client_secret="SECRET",
        http=http,
    )
    store.set_tokens("OLD", refresh_token="", expires_in=30)

    assert store.get_access_token() == "NEW"
    assert len(calls) == 1
    body = calls[0]
    assert "grant_type=fb_exchange_token" in body
    assert "fb_exchange_token=OLD" in body
    assert "refresh_token=" not in body


def test_meta_lifecycle_refresh_does_not_require_refresh_token(tmp_path, monkeypatch):
    lifecycle = TokenLifecycleStore(tmp_path)
    lifecycle.rotate("instagram", "a1", access_token="OLD", refresh_token="", expires_at=time.time() + 30)

    class FakeStore:
        def get_access_token(self):
            lifecycle.rotate("instagram", "a1", access_token="NEW", refresh_token="", expires_at=time.time() + 3600)
            return "NEW"

    monkeypatch.setattr(
        "orchestrator.platforms.token_store.make_meta_token_store",
        lambda *a, **kw: FakeStore(),
    )
    assert lifecycle.refresh_expiring("instagram", "a1", skew_sec=600) == "refreshed"
    assert lifecycle.load("instagram", "a1").access_token == "NEW"


def _telegram_setup(tmp_path):
    cfg = load_config("config.ci.yaml")
    db = Database(tmp_path / "tg.sqlite")
    from orchestrator.clock import FakeClock
    clock = FakeClock()
    notifier = TelegramNotifier(cfg, db, clock)
    setup_commands(notifier, {"db": db, "cfg": cfg, "safety": None, "scheduler": None, "clock": clock})
    return notifier, db


def test_telegram_claim_commands_are_account_scoped(tmp_path):
    bot, db = _telegram_setup(tmp_path)
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, account_id, status, external_id) "
        "VALUES ('long_video', 7, 'youtube', 'a1', 'scheduled', 'A1')"
    )
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, account_id, status, external_id) "
        "VALUES ('long_video', 7, 'youtube', 'a2', 'scheduled', 'A2')"
    )

    assert bot.handle_update(7004751908, "/claims_keep long_video 7 youtube a1")
    rows = db.fetchall(
        "SELECT account_id, claims_state FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=7 AND platform='youtube' ORDER BY account_id"
    )
    assert rows == [{"account_id": "a1", "claims_state": "kept"}, {"account_id": "a2", "claims_state": None}]

    msg = bot.handle_update(7004751908, "/claims_a3 long_video 7 youtube")
    assert "requires account_id" in msg
    assert db.fetchone(
        "SELECT status FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=7 AND platform='youtube' AND account_id='a2'"
    )["status"] == "scheduled"


def test_claim_notification_carries_account_id(tmp_path):
    cfg = load_config("config.ci.yaml")
    db = Database(tmp_path / "tg.sqlite")
    notifier = TelegramNotifier(cfg, db, FakeClock())
    sent = []
    notifier.broadcast_markup = lambda text, markup: sent.append(markup)  # type: ignore[method-assign]
    notifier.ask_claims("long_video", 3, "EXT", "acct-7")
    buttons = sent[0]["inline_keyboard"][0]
    callbacks = [b["callback_data"] for b in buttons]
    assert "claims_a3 long_video 3 youtube acct-7" in callbacks
    assert "claims_keep long_video 3 youtube acct-7" in callbacks


def test_token_lifecycle_path_cannot_escape_root(tmp_path):
    store = TokenLifecycleStore(tmp_path)
    path = store.path("instagram", "../../outside/token")
    assert path.parent == tmp_path.resolve()
    assert path.name.startswith("instagram__")
    assert "/" not in path.name and "\x00" not in path.name


def test_tg_voice_quotes_remote_path(tmp_path):
    import tools.tg_voice as tg_voice

    calls = []

    class R:
        returncode = 0
        stdout = b"voice"

    original = tg_voice.subprocess.run
    try:
        tg_voice.subprocess.run = lambda *args, **kwargs: (calls.append(args[0]) or R())
        assert tg_voice.fetch_voice("audio/x; touch /tmp/pwn", tmp_path / "voice.ogg", tries=1)
    finally:
        tg_voice.subprocess.run = original

    command = calls[0][-1]
    assert command == "cat -- '/opt/orchestrator/audio/x; touch /tmp/pwn'"
    assert command.startswith("cat -- ")



def test_bare_pass_inventory_is_reviewed():
    import ast
    from collections import Counter
    from pathlib import Path
    root = Path("src/orchestrator")
    counts = Counter()
    for path in root.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and any(isinstance(stmt, ast.Pass) for stmt in node.body):
                counts[str(path)] += 1
    assert dict(sorted(counts.items())) == {}


def test_cloudflared_public_url_does_not_embed_access_key():
    from pathlib import Path
    text = Path("scripts/cloudflared_url_sync.sh").read_text()
    assert "?key=$KEY" not in text
    assert "PUB=\"$URL/webapp/b/$BUILD/\"" in text


def test_social_gate_isolates_provider_state():
    from pathlib import Path
    text = Path("scripts/gate_social_architecture.sh").read_text()
    assert "TIKTOK_INBOX_PATH=\"$SOCIAL_GATE_TMP/tiktok_inbox.json\"" in text
    assert "mktemp -d" in text
