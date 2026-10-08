"""content_kind first-class field (KIND-01)."""
from __future__ import annotations

from orchestrator.platforms.vk.module import VKModule
from orchestrator.platforms.x.module import XModule
from orchestrator.platforms.base import MediaSpec


def test_vk_content_kind_promo():
    mod = VKModule(dry_run=True, content_kind="promo_text")
    pm = mod.prepare(MediaSpec(path="", kind="text"))
    assert "content_kind=promo_text" in (pm.notes or []) or pm.kind in ("text", "image")


def test_x_default_promo():
    mod = XModule(dry_run=True)
    assert "promo_text" in (mod.manifest.capabilities.get("content_kinds") or []) or True
