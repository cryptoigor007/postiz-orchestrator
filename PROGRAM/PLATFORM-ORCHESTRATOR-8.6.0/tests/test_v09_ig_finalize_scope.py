from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.orchestrator.runner import Runner


class FakeDB:
    def __init__(self):
        self.path = "/tmp/fake-db.sqlite"
        self.queries = []
        self.updates = []

    def fetchall(self, sql, params):
        self.queries.append((sql, tuple(params)))
        assert "AND account_id=?" in sql
        assert tuple(params)[-1] == "acct-1"
        return [
            {
                "entity_type": "short",
                "entity_id": 1,
                "account_id": "acct-1",
                "external_id": "container-1",
                "external_sub_id": None,
                "scheduled_for": "2026-10-02T12:00:00+00:00",
            }
        ]

    def execute(self, sql, params):
        self.updates.append((sql, tuple(params)))
        return 1


class FakeClock:
    def now(self):
        return datetime(2026, 10, 2, 11, 45, tzinfo=timezone.utc)


class FakeInstagram:
    def __init__(self):
        self.finalized = []

    def finalize_container(self, cid):
        self.finalized.append(cid)


class FakeRegistry:
    def __init__(self, mod):
        self.mod = mod
        self.created = []

    def has(self, platform):
        return platform == "instagram"

    def create(self, platform, **kwargs):
        self.created.append((platform, kwargs))
        return self.mod


def test_ig_finalize_scopes_select_to_configured_account():
    db = FakeDB()
    mod = FakeInstagram()
    registry = FakeRegistry(mod)
    cfg = SimpleNamespace(
        platforms={"instagram": SimpleNamespace(account_id="acct-1")},
        timezone="UTC",
        daily_ahead=SimpleNamespace(enabled=False),
    )
    runner = Runner.__new__(Runner)
    runner.comps = {
        "db": db,
        "clock": FakeClock(),
        "module_registry": registry,
        "media_transfer": SimpleNamespace(media_host=None),
    }
    runner.cfg = cfg
    runner.dry_run = False

    with patch("src.orchestrator.auth_tokens.token_provider_for", return_value=lambda: None):
        runner._cycle_ig_finalize()

    assert len(db.queries) == 1
    assert len(registry.created) == 1
    assert registry.created[0][1]["account_id"] == "acct-1"
    assert mod.finalized == ["container-1"]


def test_ig_finalize_fails_closed_on_ambiguous_account_scope():
    db = FakeDB()
    db.fetchall = lambda _sql, _params=None: [
        {"account_id": "acct-1", "entity_type": "short", "entity_id": 1, "external_id": "c1", "external_sub_id": None, "scheduled_for": "2026-10-02T12:00:00+00:00"},
        {"account_id": "acct-2", "entity_type": "short", "entity_id": 2, "external_id": "c2", "external_sub_id": None, "scheduled_for": "2026-10-02T12:00:00+00:00"},
    ]
    mod = FakeInstagram()
    registry = FakeRegistry(mod)
    cfg = SimpleNamespace(
        platforms={"instagram": SimpleNamespace(account_id="")},
        timezone="UTC",
        daily_ahead=SimpleNamespace(enabled=False),
    )
    runner = Runner.__new__(Runner)
    runner.comps = {"db": db, "clock": FakeClock(), "module_registry": registry, "media_transfer": SimpleNamespace(media_host=None)}
    runner.cfg = cfg
    runner.dry_run = False
    runner._cycle_ig_finalize()
    assert mod.finalized == []
