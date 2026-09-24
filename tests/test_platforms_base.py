"""Тесты каркаса платформенных модулей (Э1).

Проверяем: манифест (валидация), реестр, разрешение engines, таксономию ошибок
и поведение базового контракта PlatformModule.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import yaml

from orchestrator.platforms import (
    ModuleRegistry,
    load_modules,
    modules_status,
    resolve_engine,
)
from orchestrator.platforms.base import (
    AuthStatus,
    ClaimsResult,
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    NotSupported,
    PlatformModule,
    PreparedMedia,
)
from orchestrator.platforms.manifest import ManifestError, ModuleManifest, load_manifest


def _manifest_dict(**overrides):
    data = {
        "id": "demo",
        "name": "Demo",
        "api_version": "v1",
        "module_version": "1.0.0",
        "core_min": "8.5.0",
        "auth": {"method": "oauth2_authorization_code", "scopes": ["basic"], "broker_key": "demo"},
        "capabilities": {"publish": True, "claims_check": "manual"},
        "limits": {"posts_per_day": 1},
        "media": {"video": {"container": "mp4"}},
        "statuses": {"published": ["published"]},
        "docs": "MODULE_DEMO.txt",
    }
    data.update(overrides)
    return data


class DummyModule(PlatformModule):
    manifest = ModuleManifest.from_dict(_manifest_dict())

    def __init__(self, **kwargs) -> None:
        self.deps = kwargs

    def auth_status(self) -> AuthStatus:
        return AuthStatus(ok=True, account="demo")


# ---------------------------------------------------------------- манифест ----
def test_manifest_loads_from_file(tmp_path):
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(_manifest_dict()), encoding="utf-8")
    manifest = load_manifest(path)
    assert manifest.id == "demo"
    assert manifest.capabilities["publish"] is True
    assert manifest.claims_check() == "manual"
    assert manifest.capability("publish") is True
    assert manifest.capability("delete") is False


def test_manifest_missing_required_fields():
    with pytest.raises(ManifestError) as exc:
        ModuleManifest.from_dict({"id": "x"})
    assert "отсутствуют обязательные поля" in str(exc.value)


def test_manifest_unknown_capability_rejected():
    data = _manifest_dict(capabilities={"publish": True, "warp": True})
    with pytest.raises(ManifestError):
        ModuleManifest.from_dict(data)


def test_manifest_bad_claims_value_rejected():
    data = _manifest_dict(capabilities={"publish": True, "claims_check": "maybe"})
    with pytest.raises(ManifestError):
        ModuleManifest.from_dict(data)


def test_manifest_missing_file(tmp_path):
    with pytest.raises(ManifestError):
        load_manifest(tmp_path / "nope.yaml")


# ------------------------------------------------------------------ реестр ----
def test_resolve_engine_module_and_aliases():
    direct = resolve_engine("direct")
    assert direct.kind == "module" and direct.module_id == "youtube"
    explicit = resolve_engine("module:YouTube")
    assert explicit.kind == "module" and explicit.module_id == "youtube"
    adapter = resolve_engine("postiz")
    assert adapter.kind == "postiz" and adapter.module_id is None


def test_resolve_engine_unknown_raises():
    with pytest.raises(ValueError):
        resolve_engine("teleport")


def test_registry_create_missing_module_raises_fatal():
    registry = ModuleRegistry()
    with pytest.raises(ModuleError) as exc:
        registry.create("unknown")
    assert exc.value.code is ModuleErrorCode.FATAL
    assert exc.value.retryable is False


def test_load_modules_skips_adapters_and_builds_modules():
    registry = ModuleRegistry()
    registry.register("demo", DummyModule)
    modules = load_modules(
        {"youtube": "module:demo", "telegram": "postiz"},
        registry=registry,
        deps={"token": "x"},
    )
    assert set(modules) == {"youtube"}
    assert isinstance(modules["youtube"], DummyModule)
    assert modules["youtube"].deps == {"token": "x"}


def test_modules_status_reports_availability():
    registry = ModuleRegistry()
    registry.register("demo", DummyModule)
    report = modules_status(
        {"youtube": "module:demo", "instagram": "module:instagram", "telegram": "postiz"},
        registry=registry,
    )
    by_platform = {item["platform"]: item for item in report}
    assert by_platform["youtube"]["available"] is True
    assert by_platform["instagram"]["available"] is False
    assert by_platform["telegram"]["kind"] == "postiz"


# ------------------------------------------------------- базовый контракт ----
def test_module_error_retryable_defaults():
    transient = ModuleError(ModuleErrorCode.TRANSIENT, "сеть")
    media = ModuleError(ModuleErrorCode.MEDIA_INVALID, "битый файл")
    assert transient.retryable is True
    assert media.retryable is False
    assert media.action == ""


def test_default_methods_raise_not_supported():
    module = DummyModule()
    with pytest.raises(NotSupported):
        module.upload(PreparedMedia(path="/tmp/a.mp4"), meta=None)  # type: ignore[arg-type]
    with pytest.raises(NotSupported):
        module.get_status("abc")


def test_default_claims_and_prepare():
    module = DummyModule()
    claims = module.check_claims("abc")
    assert isinstance(claims, ClaimsResult) and claims.supported is False
    prepared = module.prepare(MediaSpec(path="/tmp/video.mp4"))
    assert prepared.path == "/tmp/video.mp4" and prepared.kind == "video"
    assert module.validate_config({}) == []


def test_auth_status_abstract_contract():
    module = DummyModule()
    assert module.auth_status().ok is True
    assert isinstance(datetime.now(UTC), datetime)  # sanity: tz-aware now доступен
