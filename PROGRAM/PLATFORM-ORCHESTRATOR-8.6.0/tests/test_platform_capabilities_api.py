"""UX-02 platform_capabilities endpoint."""
from __future__ import annotations

from orchestrator.webapp_api import WebAppAPI


class _Cfg:
    platforms = {
        "youtube": type("P", (), {"enabled": True, "content_kind_default": "video_native"})(),
        "telegram": type("P", (), {"enabled": True, "content_kind_default": ""})(),
    }


def test_platform_capabilities_shape():
    # Minimal comps — method should not crash
    api = WebAppAPI.__new__(WebAppAPI)
    api.cfg = _Cfg()
    api.comps = {"modules": {}}
    out = api._platform_capabilities()
    assert "items" in out
    names = {i["platform"] for i in out["items"]}
    assert "youtube" in names or "telegram" in names
