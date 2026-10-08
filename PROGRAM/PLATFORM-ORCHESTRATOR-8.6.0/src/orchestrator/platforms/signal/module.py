from __future__ import annotations

from pathlib import Path
from typing import Any

from ..base import AuthStatus, ModuleError, ModuleErrorCode, PlatformModule, NotSupported
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class SignalFeasibilityModule(PlatformModule):
    """Explicit feasibility boundary for Signal.

    Signal's official technical documentation publishes the Signal Protocol and
    software-library specifications, not a general server-side publisher/bot API.
    Until an official business/bot transport is exposed, this module must remain
    non-publishing rather than using unofficial wrappers or browser automation.
    """

    def __init__(self, **_: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)

    def auth_status(self) -> AuthStatus:
        return AuthStatus(False, account="signal", details="Official server-side publishing/bot API not confirmed; Signal documents protocol/software libraries only")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        return ["signal: official server-side publishing/bot API is not confirmed"]

    def publish(self, *args: Any, **kwargs: Any):
        raise ModuleError(ModuleErrorCode.DEPENDENCY_DOWN, "Signal: official server-side publishing transport is unavailable")


def create_module(**deps: Any) -> SignalFeasibilityModule:
    return SignalFeasibilityModule(**deps)
