from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.engines.registry import REGISTRY, capabilities, select_engine
from orchestrator.engines.base import PublishResult


def test_capabilities_matrix():
    assert capabilities("postiz")["publish"] is True
    assert capabilities("postiz")["list"] is False
    assert capabilities("direct")["list"] is True
    assert capabilities("direct")["update"] is True
    assert capabilities("n8n")["publish"] is True
    assert capabilities("browser")["experimental"] is True
    assert capabilities("unknown-engine") == {}


def test_select_engine_from_config():
    class C:
        def engine_for(self, platform):
            return {"youtube": "direct"}.get(platform, "postiz")

    assert select_engine(C(), "youtube") == "direct"
    assert select_engine(C(), "telegram") == "postiz"


def test_publish_result_shape():
    r = PublishResult(engine="postiz", platform="telegram", external_id="1",
                      url="https://t.me/x/1", state="scheduled")
    assert r.engine == "postiz"
    assert REGISTRY["direct"]["delete"] is True
