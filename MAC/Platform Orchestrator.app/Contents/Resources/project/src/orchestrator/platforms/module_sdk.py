from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .base import PlatformModule
from .manifest import ModuleManifest

SDK_VERSION = "1.0.0"
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


class ModuleCompatibilityError(ValueError):
    pass


def _parts(version: str) -> tuple[int, int, int]:
    base = str(version or "0.0.0").split("+", 1)[0].split("-", 1)[0]
    bits = base.split(".")
    return tuple(int(bits[i]) for i in range(3))  # type: ignore[return-value]


def version_gte(current: str, minimum: str) -> bool:
    return _parts(current) >= _parts(minimum)


@dataclass(frozen=True)
class ModuleSDKContract:
    sdk_version: str = SDK_VERSION
    compatibility: str = "backward_compatible"


class ModuleSDK:
    """Stable internal provider contract gate."""

    contract = ModuleSDKContract()

    @classmethod
    def validate_manifest(cls, manifest: ModuleManifest) -> None:
        module_version = str(manifest.module_version or "")
        if not _SEMVER.fullmatch(module_version):
            raise ModuleCompatibilityError(
                f"module {manifest.id!r} has invalid module_version={module_version!r}; expected semver"
            )
        sdk_min = str(getattr(manifest, "sdk_min", "1.0.0") or "1.0.0")
        if not re.fullmatch(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$", sdk_min):
            raise ModuleCompatibilityError(f"module {manifest.id!r} has invalid sdk_min={sdk_min!r}")
        if not version_gte(cls.contract.sdk_version, sdk_min):
            raise ModuleCompatibilityError(
                f"module {manifest.id!r} requires module-sdk>={sdk_min}, current={cls.contract.sdk_version}"
            )
        policy = str(getattr(manifest, "sdk_policy", "backward_compatible") or "backward_compatible")
        if policy not in {"backward_compatible", "pinned", "breaking"}:
            raise ModuleCompatibilityError(f"module {manifest.id!r} has invalid version_policy={policy!r}")
        if policy == "breaking" and _parts(sdk_min)[0] != _parts(cls.contract.sdk_version)[0]:
            raise ModuleCompatibilityError(
                f"module {manifest.id!r} declares breaking SDK policy outside current major"
            )

    @classmethod
    def validate_instance(cls, module: PlatformModule) -> None:
        manifest = getattr(module, "manifest", None)
        if not isinstance(manifest, ModuleManifest):
            raise ModuleCompatibilityError("module has no valid ModuleManifest")
        cls.validate_manifest(manifest)
        strict = bool(getattr(manifest, "extra", {}).get("contract_strict", False))
        if not strict:
            return
        cap_to_method = {
            "publish": "publish",
            "schedule_publish": "schedule_publish",
            "update_metadata": "update_metadata",
            "delete": "delete",
        }
        for cap, method_name in cap_to_method.items():
            if not bool(manifest.capabilities.get(cap, False)):
                continue
            impl = getattr(type(module), method_name, None)
            base = getattr(PlatformModule, method_name, None)
            if impl is base:
                raise ModuleCompatibilityError(
                    f"module {manifest.id!r} advertises {cap}=true but does not implement {method_name}()"
                )


def sdk_info() -> dict[str, Any]:
    return {"version": SDK_VERSION, "compatibility": "backward_compatible"}
