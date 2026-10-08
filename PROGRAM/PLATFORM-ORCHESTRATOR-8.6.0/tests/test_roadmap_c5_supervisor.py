from __future__ import annotations
import threading
import time
from orchestrator.db import Database
from orchestrator.provider_supervisor import ProviderSupervisor


def test_provider_queue_isolated_by_account(tmp_path):
    db = Database(tmp_path / "s.sqlite")
    sup = ProviderSupervisor(db)
    entered = threading.Event(); release = threading.Event(); seen=[]
    def first():
        with sup.queue("instagram", "a1") as ok:
            seen.append(("a1", ok)); entered.set(); release.wait(2)
    t = threading.Thread(target=first); t.start(); entered.wait(2)
    with sup.queue("instagram", "a1", timeout=0) as ok_same:
        assert ok_same is False
    with sup.queue("instagram", "a2", timeout=0) as ok_other:
        assert ok_other is True
    release.set(); t.join(2)
    assert seen == [("a1", True)]


def test_supervisor_probe_recovers_half_open(tmp_path):
    db = Database(tmp_path / "p.sqlite")
    sup = ProviderSupervisor(db, failure_threshold=1, cooldown_sec=1)
    sup.record_failure("x", "a", "boom")
    assert not sup.allow("x", "a")
    time.sleep(1.05)
    calls=[]
    assert sup.run_probe("x", "a", lambda: calls.append(1)) is True
    assert calls == [1]
    assert sup.state("x", "a") == "healthy"
