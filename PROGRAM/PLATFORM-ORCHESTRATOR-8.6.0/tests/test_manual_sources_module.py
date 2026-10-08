"""engines.module:* in manual_sources (module path default)."""

from __future__ import annotations

from types import SimpleNamespace

from orchestrator.manual_sources import build_manual_sources
from orchestrator.platforms.base import PlatformModule


def test_build_manual_sources_module_youtube_dry():
    cfg = SimpleNamespace(
        platforms={
            "youtube": SimpleNamespace(enabled=True, account_id="", integration_id=""),
        },
        engine_for=lambda p: "module:youtube",
    )
    sources = build_manual_sources(cfg, env={})
    assert "youtube" in sources
    mod = sources["youtube"]
    assert isinstance(mod, PlatformModule)
    assert mod.manifest.id == "youtube"


def test_build_manual_sources_platform_engine_skipped():
    """platform engine string yields no source (platformEngine removed)."""
    cfg = SimpleNamespace(
        platforms={"telegram": SimpleNamespace(enabled=True, account_id="")},
        engine_for=lambda p: "platform",
    )
    sources = build_manual_sources(cfg, env={})
    assert "telegram" not in sources
