"""Regression for residual P2/Q closures (8.0.0)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.metrics import sanitize_metrics
from orchestrator.safety import SafetyChecker
from orchestrator.webapp_api import WEBAPP_BUILD, WebAppAPI

ROOT = Path(__file__).resolve().parents[1]


def test_sanitize_metrics_strips_secrets():
    data = {"cycles": 1, "api_token": "secret", "nested": {"password": "x", "ok": 1}}
    out = sanitize_metrics(data)
    assert "api_token" not in out
    assert out["cycles"] == 1
    assert "password" not in out.get("nested", {})
    assert out["nested"]["ok"] == 1


def test_webapp_build_no_dots():
    assert "." not in WEBAPP_BUILD


def test_exception_day_blocks(tmp_path):
    db = Database(str(tmp_path / "t.sqlite"))
    cfg = load_config(ROOT / "config.yaml")
    clock = FakeClock(datetime(2026, 6, 15, 12, 0, tzinfo=UTC))
    safety = SafetyChecker(db, cfg, clock)
    from orchestrator import sched_settings as ss
    day = "2026-06-15"
    platform = next(iter(cfg.platforms))
    ss.save_schedule_settings(db, {platform: {"exception_days": [day]}})
    ok, reason = safety.can_schedule(platform, clock.now() + timedelta(hours=2), 10)
    assert ok is False
    assert reason == "exception_day"


def test_read_only_blocks_schedule(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCH_READ_ONLY", "1")
    monkeypatch.setenv("WEBAPP_ACCESS_KEY", "testkey")
    db = Database(str(tmp_path / "t.sqlite"))
    cfg = load_config(ROOT / "config.yaml")
    clock = FakeClock(datetime(2026, 6, 15, 12, 0, tzinfo=UTC))
    api = WebAppAPI({"cfg": cfg, "db": db, "clock": clock})
    code, body, _ = api.handle(
        "POST", "/webapp/api/schedule",
        {"X-Webapp-Key": "testkey"}, b"{}",
    )
    assert code == 403
    assert body.get("error") == "read_only" or (isinstance(body, dict) and "read_only" in str(body))


def test_overflow_batch_cap_exists():
    src = (ROOT / "src/orchestrator/overflow.py").read_text()
    assert "MAX_OVERFLOW_BATCH" in src


def test_broker_sql_rejects_injection():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import token_broker as tb
    with pytest.raises(ValueError):
        tb.build_token_sql("you';tube")
    sql = tb.build_token_sql("youtube", "abc-1")
    assert "youtube" in sql and "abc-1" in sql


def test_read_only_blocks_all_mutations(tmp_path, monkeypatch):
    """read-only должен блокировать ВСЕ мутирующие маршруты (не только schedule)."""
    import json as _json


    monkeypatch.setenv("ORCH_READ_ONLY", "1")
    monkeypatch.setenv("WEBAPP_DEV", "1")
    from orchestrator.config import load_config
    from orchestrator.db import Database
    from orchestrator.webapp_api import WebAppAPI

    db = Database(tmp_path / "ro.sqlite")
    cfg = load_config(__import__("pathlib").Path(__file__).resolve().parents[1] / "config.yaml")
    api = WebAppAPI({"cfg": cfg, "db": db})
    cases = [
        ("/webapp/api/schedule", {"async": True}),
        ("/webapp/api/distribute", {}),
        ("/webapp/api/sync", {}),
        ("/webapp/api/reconcile", {}),
        ("/webapp/api/backup", {}),
        ("/webapp/api/scheduling_mode", {"mode": "auto"}),
        ("/webapp/api/pause_platform", {"platform": "youtube"}),
        ("/webapp/api/resume_platform", {"platform": "youtube"}),
        ("/webapp/api/queue/restore", {"all": True}),
        ("/webapp/api/queue/remove", {"entity_type": "short", "entity_id": 1}),
        ("/webapp/api/series_end", {"platform": "youtube", "enable": False}),
        ("/webapp/api/manual/scan", {}),
        ("/webapp/api/roots", {"items": []}),
    ]
    for path, body in cases:
        code, payload, _ = api.handle("POST", path, {"X-Telegram-Init-Data": "dev"},
                                      _json.dumps(body).encode())
        assert code == 403 and payload.get("error") == "read_only", (path, code, payload)
