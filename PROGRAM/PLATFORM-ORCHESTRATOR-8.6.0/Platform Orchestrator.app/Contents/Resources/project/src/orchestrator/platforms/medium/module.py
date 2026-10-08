from __future__ import annotations

from pathlib import Path
from typing import Any

from ..base import AuthStatus, ModuleError, ModuleErrorCode, PlatformModule
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class MediumDeprecatedModule(PlatformModule):
    """Explicit deprecation boundary for Medium.

    Medium's archived official API documentation states that the API is no longer
    supported and that new integrations are not accepted. The orchestrator therefore
    refuses to publish and does not ship a transport that implies live support.
    """

    def __init__(self, **_: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)

    def auth_status(self) -> AuthStatus:
        return AuthStatus(False, account="medium", details="Medium API is no longer supported; new integrations are not accepted")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        return ["medium: API deprecated; new integrations are not accepted"]

    def publish(self, *args: Any, **kwargs: Any):
        raise ModuleError(ModuleErrorCode.API_DEPRECATED, "Medium: API is no longer supported")

    def list_remote_items(self, *args: Any, **kwargs: Any):
        raise ModuleError(ModuleErrorCode.API_DEPRECATED, "Medium: API is no longer supported")

    def get_status(self, external_id: str):
        raise ModuleError(ModuleErrorCode.API_DEPRECATED, "Medium: API is no longer supported")


def create_module(**deps: Any) -> MediumDeprecatedModule:
    return MediumDeprecatedModule()
