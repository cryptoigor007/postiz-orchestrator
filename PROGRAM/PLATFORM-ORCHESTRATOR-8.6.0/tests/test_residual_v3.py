from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from orchestrator.backlog import BacklogManager
from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.media_transfer import MediaTransferManager, MediaArtifact
from orchestrator.platforms.base import ModuleError, ModuleErrorCode
from orchestrator.reconciliation import ModuleReconciliation, ReconStatusFailure
from orchestrator.safety import SafetyChecker
from orchestrator.webapp_api import WebAppAPI

ROOT = Path(__file__).resolve().parents[1]


def _env(tmp_path):
    cfg = load_config(ROOT / "config.ci.yaml")
    db = Database(tmp_path / "t.sqlite")
    clock = FakeClock(datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    db.ensure_platform_states(list(cfg.platforms.keys()))
    return cfg, db, clock


def test_reconciliation_auth_failure_never_increments_missing(tmp_path):
    cfg, db, clock = _env(tmp_path)
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,external_id) VALUES('short',1,'youtube','acct','published','remote-1')")
    rec = ModuleReconciliation(db, cfg, clock)
    rec._module_status = lambda *_args, **_kw: ReconStatusFailure("AUTH_EXPIRED", "expired")
    out = rec.run()
    row = db.fetchone("SELECT status,last_error FROM entity_platform_status WHERE entity_type='short' AND entity_id=1 AND platform='youtube' AND account_id='acct'")
    assert row["status"] == "published"
    assert row["last_error"].startswith("status_sync_error:AUTH_EXPIRED:")
    assert out.missing == 0
    assert out.errors


def test_safety_isolated_per_account(tmp_path):
    cfg, db, clock = _env(tmp_path)
    safety = SafetyChecker(db, cfg, clock)
    safety.pause_platform("youtube", "auth", account_id="acct-1")
    assert safety.is_platform_paused("youtube", "acct-1") is True
    assert safety.is_platform_paused("youtube", "acct-2") is False
    safety.resume_platform("youtube", account_id="acct-1")
    assert safety.is_platform_paused("youtube", "acct-1") is False


def test_backlog_state_isolated_per_account(tmp_path):
    cfg, db, clock = _env(tmp_path)
    mgr = BacklogManager(db, cfg, clock)
    mgr.ask("youtube", clock.now() + timedelta(hours=1), account_id="acct-1")
    assert mgr.awaiting("youtube", "acct-1") is True
    assert mgr.awaiting("youtube", "acct-2") is False
    assert db.fetchone("SELECT 1 FROM platform_queue_account_state WHERE platform='youtube' AND account_id='acct-1'") is not None


def test_webapp_rate_limit_persists_across_instances(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_DEV", "1")
    monkeypatch.setenv("WEBAPP_RATE_LIMIT", "2")
    cfg, db, clock = _env(tmp_path)
    a = WebAppAPI({"cfg": cfg, "db": db, "clock": clock})
    headers = {"X-Telegram-Init-Data": "dev"}
    assert a.handle("GET", "/webapp/api/status", headers, b"")[0] == 200
    assert a.handle("GET", "/webapp/api/status", headers, b"")[0] == 200
    b = WebAppAPI({"cfg": cfg, "db": db, "clock": clock})
    assert b.handle("GET", "/webapp/api/status", headers, b"")[0] == 429


def test_media_fetch_uses_resolved_ip_without_second_dns(monkeypatch, tmp_path):
    import urllib3
    from types import SimpleNamespace
    manager = MediaTransferManager(temp_dir=tmp_path, max_download_bytes=1024)
    monkeypatch.setattr(manager, "validate_url", lambda _url: None)
    monkeypatch.setattr(manager, "_resolve_public_ips", lambda _url: ("example.test", 80, ["93.184.216.34"]))
    seen = {}
    class Resp:
        status = 200
        headers = {"Content-Type": "video/mp4"}
        def read(self, _n):
            if getattr(self, "done", False): return b""
            self.done = True
            return b"abc"
        def release_conn(self): pass
    class Pool:
        def __init__(self, host, port, **kw):
            seen.update(host=host, port=port, kwargs=kw)
        def request(self, *args, **kwargs): return Resp()
        def close(self): pass
    monkeypatch.setattr(urllib3, "HTTPConnectionPool", Pool)
    art = manager.fetch_url("http://example.test/video.mp4")
    assert art.sha256
    assert seen["host"] == "93.184.216.34"
    assert seen["kwargs"]["headers"]["Host"] == "example.test"


def test_reconciliation_transient_failure_never_increments_missing(tmp_path):
    cfg, db, clock = _env(tmp_path)
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,external_id) VALUES('short',2,'youtube','acct','published','remote-2')")
    rec = ModuleReconciliation(db, cfg, clock)
    rec._module_status = lambda *_args, **_kw: ReconStatusFailure("FATAL", "timeout")
    out = rec.run()
    row = db.fetchone("SELECT status,last_error FROM entity_platform_status WHERE entity_type='short' AND entity_id=2 AND platform='youtube' AND account_id='acct'")
    assert row["status"] == "published"
    assert row["last_error"].startswith("status_sync_error:FATAL:")
    assert out.missing == 0


def test_media_fetch_dns_flip_is_not_re_resolved_before_connect(monkeypatch, tmp_path):
    import socket
    import urllib3
    manager = MediaTransferManager(temp_dir=tmp_path, max_download_bytes=1024)
    calls = []
    def fake_getaddrinfo(host, port, **kwargs):
        calls.append((host, port))
        # A second lookup would return a private target and expose the TOCTOU.
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34' if len(calls) == 1 else '127.0.0.1', port))]
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    seen = {}
    class Resp:
        status = 200
        headers = {"Content-Type": "video/mp4"}
        def __init__(self): self.done = False
        def read(self, _n):
            if self.done: return b""
            self.done = True
            return b"abc"
        def release_conn(self): pass
    class Pool:
        def __init__(self, host, port, **kw): seen.update(host=host, port=port, kwargs=kw)
        def request(self, *args, **kwargs): return Resp()
        def close(self): pass
    monkeypatch.setattr(urllib3, "HTTPConnectionPool", Pool)
    art = manager.fetch_url("http://example.test/video.mp4")
    assert art.sha256
    assert calls == [("example.test", 80)]
    assert seen["host"] == "93.184.216.34"


def test_backlog_requires_scope_when_multiple_accounts(tmp_path):
    cfg, db, clock = _env(tmp_path)
    mgr = BacklogManager(db, cfg, clock)
    for aid in ("acct-1", "acct-2"):
        db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES('short',?,?,?, 'ready')", (1 if aid == 'acct-1' else 2, 'youtube', aid))
    import pytest
    with pytest.raises(ValueError, match="account_scope_required:youtube"):
        mgr.awaiting("youtube")


def test_manual_uploads_requires_scope_when_multiple_accounts(tmp_path):
    from orchestrator.manual_uploads import ManualUploadsService
    cfg, db, clock = _env(tmp_path)
    svc = ManualUploadsService(db, cfg, clock)
    for aid in ("acct-1", "acct-2"):
        db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES('short',?,?,?, 'ready')", (10 if aid == 'acct-1' else 11, 'youtube', aid))
    import pytest
    with pytest.raises(ValueError, match="account_scope_required:youtube"):
        svc._entities("youtube")
