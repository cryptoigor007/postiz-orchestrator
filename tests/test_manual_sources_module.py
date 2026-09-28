"""Интеграция engines.module:* в manual_sources (P2, без прод-включения)."""

from __future__ import annotations

from types import SimpleNamespace

from orchestrator.manual_sources import build_manual_sources
from orchestrator.platforms.base import PlatformModule


def test_build_manual_sources_module_youtube_dry():
    cfg = SimpleNamespace(
        platforms={
            "youtube": SimpleNamespace(enabled=True, integration_id=""),
        },
        engine_for=lambda p: "module:youtube",
    )
    sources = build_manual_sources(cfg, postiz=None, env={})
    assert "youtube" in sources
    mod = sources["youtube"]
    assert isinstance(mod, PlatformModule)
    # без токена / dry — auth может быть false; создаётся модуль
    assert mod.manifest.id == "youtube"


def test_build_manual_sources_postiz_unchanged():
    class FakePostiz:
        pass

    cfg = SimpleNamespace(
        platforms={"telegram": SimpleNamespace(enabled=True)},
        engine_for=lambda p: "postiz",
    )
    sources = build_manual_sources(cfg, postiz=FakePostiz(), env={})
    assert "telegram" in sources
    assert sources["telegram"].__class__.__name__ == "PostizEngine"
