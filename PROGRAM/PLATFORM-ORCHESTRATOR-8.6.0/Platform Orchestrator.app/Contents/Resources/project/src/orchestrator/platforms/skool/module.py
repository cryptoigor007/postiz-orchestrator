from __future__ import annotations

from pathlib import Path
from typing import Any

from ..base import AuthStatus, ModuleError, ModuleErrorCode, PlatformModule
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class SkoolFeasibilityModule(PlatformModule):
    """Explicit feasibility boundary for Skool.

    No official direct third-party REST publishing contract was verified for the
    orchestrator. The module therefore refuses direct publishing instead of
    binding the product to an unofficial API or scraping/browser automation.
    """

    def __init__(self, **_: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)

    def auth_status(self) -> AuthStatus:
        return AuthStatus(False, account="skool", details="Official direct server-side publishing contract not confirmed")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        return ["skool: official direct publishing API contract is not confirmed"]

    def publish(self, *args: Any, **kwargs: Any):
        raise ModuleError(ModuleErrorCode.DEPENDENCY_DOWN, "Skool: direct official publishing transport is unavailable")


def create_module(**deps: Any) -> SkoolFeasibilityModule:
    return SkoolFeasibilityModule()
