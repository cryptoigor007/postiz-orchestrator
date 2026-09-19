from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.postiz import MockPostizClient
from orchestrator.engines.postiz_engine import PostizEngine


def test_postiz_engine_publish_delegates():
    client = MockPostizClient()
    eng = PostizEngine(client)
    sched = datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)
    r = eng.publish("telegram", "/tmp/v.mp4",
                    {"description": "hi", "integration_id": "int1"}, sched)
    assert r.engine == "postiz"
    assert r.platform == "telegram"
    assert r.external_id.startswith("post_")
    assert r.state == "scheduled"
    assert len(client.posts) == 1
    assert eng.capabilities()["publish"] is True


def test_postiz_engine_delete():
    client = MockPostizClient()
    eng = PostizEngine(client)
    r = eng.publish("telegram", "/tmp/v.mp4", {"description": "x", "integration_id": "i"})
    assert eng.delete(r.external_id) is True
    assert client.posts == {}
