from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.engines.n8n_engine import N8nEngine
from orchestrator.engines.browser_engine import BrowserEngine


def test_n8n_publish_and_list():
    calls = []

    def http(method, url, params, json_body, headers):
        calls.append((method, url, json_body, headers))
        if url.endswith("/postiz-uploads"):
            return {"items": [{"external_id": "a"}]}
        return {"id": "wf-1", "url": "https://youtu.be/x", "state": "scheduled"}

    eng = N8nEngine("http://n8n:5678", token="T", http=http)
    r = eng.publish("youtube", "/m/v.mp4", {"description": "d"})
    assert r.engine == "n8n" and r.external_id == "wf-1"
    assert calls[0][3]["X-N8N-Token"] == "T"
    rows = eng.list_uploads()
    assert rows[0]["external_id"] == "a"
    assert eng.capabilities()["publish"] is True


def test_browser_experimental():
    eng = BrowserEngine()
    assert eng.capabilities()["experimental"] is True
    import pytest
    with pytest.raises(NotImplementedError):
        eng.list_uploads()
