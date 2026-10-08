"""Scaffolding for provider modules whose external access/API work is still pending.

These modules are intentionally honest: they expose the module contract but do not
claim Direct Publish or Messaging support until the provider implementation exists.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import AuthStatus, PlatformModule, ModuleError, ModuleErrorCode, NotSupported
from .manifest import load_manifest


class PlannedProviderModule(PlatformModule):
    def __init__(self, *, manifest_path: str | Path, platform: str, **_deps: Any) -> None:
        self.manifest = load_manifest(manifest_path)
        self._platform = platform

    def auth_status(self) -> AuthStatus:
        return AuthStatus(ok=False, account=self._platform, details="module scaffold: provider access/API not configured")

    def publish(self, media, meta):
        raise NotSupported("publish")

    def get_status(self, external_id: str):
        raise NotSupported("get_status")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        return [f"{self._platform}: provider module scaffold only; implement official API + access before enabling"]


def make_planned_factory(platform: str, manifest_path: str | Path):
    def _factory(**deps: Any) -> PlannedProviderModule:
        return PlannedProviderModule(platform=platform, manifest_path=manifest_path, **deps)
    return _factory
