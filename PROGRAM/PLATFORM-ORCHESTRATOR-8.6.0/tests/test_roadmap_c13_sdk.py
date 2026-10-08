from __future__ import annotations

import pytest

from orchestrator.platforms import ModuleRegistry
from orchestrator.platforms.base import ModuleErrorCode, PlatformModule, PublishResult
from orchestrator.platforms.manifest import ModuleManifest
from orchestrator.platforms.module_sdk import ModuleCompatibilityError, ModuleSDK


def manifest(**overrides):
    data = dict(
        id="sdk-test",
        name="SDK Test",
        api_version="v1",
        module_version="1.0.0",
        core_min="0.0.1",
        auth={"method": "none"},
        capabilities={"publish": False, "claims_check": "unsupported"},
        limits={},
        media={},
        statuses={},
        docs="MODULE_SDK_TEST.txt",
        publish_mode="unsupported",
        sdk_policy="backward_compatible",
        sdk_min="1.0.0",
    )
    data.update(overrides)
    return ModuleManifest(**data)


def test_sdk_accepts_current_manifest():
    ModuleSDK.validate_manifest(manifest())


def test_sdk_rejects_invalid_module_semver():
    with pytest.raises(ModuleCompatibilityError, match="invalid module_version"):
        ModuleSDK.validate_manifest(manifest(module_version="dev"))


def test_sdk_rejects_future_minimum():
    with pytest.raises(ModuleCompatibilityError, match="requires module-sdk"):
        ModuleSDK.validate_manifest(manifest(sdk_min="9.0.0"))


def test_registry_converts_sdk_failure_to_fatal_module_error():
    reg = ModuleRegistry()

    class M(PlatformModule):
        manifest = manifest(module_version="broken")

        def auth_status(self):  # pragma: no cover
            return None

        def publish(self, media, meta):  # pragma: no cover
            return PublishResult(external_id="x", state="published", platform="sdk-test")

    reg.register("sdk-test", lambda **deps: M())
    with pytest.raises(Exception) as exc:
        reg.create("sdk-test")
    assert "invalid module_version" in str(exc.value)
