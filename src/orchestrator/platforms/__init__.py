"""Реестр платформенных модулей и разрешение engines.<platform>.

См. docs/dev/02_MODULE_STANDARD.txt §5:
  engines.<platform>: "module:<id>" | "postiz" | "n8n" | "browser"
Совместимость: "direct" → "module:youtube".
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .base import (  # noqa: F401  (реэкспорт для удобства потребителей)
    AuthStatus,
    ClaimsResult,
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    NotSupported,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    PublishStatus,
    UploadResult,
)
from .manifest import ManifestError, ModuleManifest, load_manifest  # noqa: F401

__all__ = [
    "AuthStatus",
    "ClaimsResult",
    "MediaSpec",
    "ModuleError",
    "ModuleErrorCode",
    "ModuleManifest",
    "ModuleRegistry",
    "NotSupported",
    "PlatformModule",
    "PreparedMedia",
    "PublishMeta",
    "PublishResult",
    "PublishStatus",
    "ResolvedEngine",
    "UploadResult",
    "default_registry",
    "load_manifest",
    "load_modules",
    "modules_status",
    "register_module",
    "resolve_engine",
]

ENGINE_ALIASES: dict[str, str] = {
    "direct": "module:youtube",  # совместимость со старым engines.youtube=direct
}

KNOWN_ADAPTERS: tuple[str, ...] = ("postiz", "n8n", "browser")


@dataclass(frozen=True)
class ResolvedEngine:
    raw: str
    kind: str  # module | postiz | n8n | browser
    module_id: str | None = None


def resolve_engine(value: str) -> ResolvedEngine:
    """Преобразовать engines.<platform> в решение: модуль или адаптер."""
    raw = str(value or "").strip()
    lowered = raw.lower()
    lowered = ENGINE_ALIASES.get(lowered, lowered)
    if lowered.startswith("module:"):
        module_id = lowered.split(":", 1)[1].strip()
        if not module_id:
            raise ValueError("engine: пустой id модуля (ожидается module:<id>)")
        return ResolvedEngine(raw=raw, kind="module", module_id=module_id)
    if lowered in KNOWN_ADAPTERS:
        return ResolvedEngine(raw=raw, kind=lowered)
    raise ValueError(f"engine: неизвестное значение {value!r}")


class ModuleRegistry:
    """Реестр фабрик модулей: id -> фабрика(**deps) -> PlatformModule."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., PlatformModule]] = {}

    def register(self, module_id: str, factory: Callable[..., PlatformModule]) -> None:
        mid = str(module_id or "").strip().lower()
        if not mid:
            raise ValueError("registry: пустой id модуля")
        self._factories[mid] = factory

    def has(self, module_id: str) -> bool:
        return str(module_id or "").strip().lower() in self._factories

    def ids(self) -> list[str]:
        return sorted(self._factories)

    def create(self, module_id: str, **deps: object) -> PlatformModule:
        mid = str(module_id or "").strip().lower()
        factory = self._factories.get(mid)
        if factory is None:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                f"модуль {module_id!r} не зарегистрирован",
                action="проверьте engines.<platform> и доступные модули",
            )
        return factory(**deps)


_default_registry = ModuleRegistry()


def register_module(module_id: str, factory: Callable[..., PlatformModule]) -> None:
    _default_registry.register(module_id, factory)


def default_registry() -> ModuleRegistry:
    return _default_registry


def load_modules(
    engines: Mapping[str, str],
    *,
    registry: ModuleRegistry | None = None,
    deps: Mapping[str, object] | None = None,
) -> dict[str, PlatformModule]:
    """Создать модули для платформ, настроенных как module:<id>.

    Адаптеры (postiz/n8n/browser) пропускаются — их обслуживает старый слой engines/.
    """
    reg = registry or _default_registry
    out: dict[str, PlatformModule] = {}
    for platform, value in (engines or {}).items():
        resolved = resolve_engine(str(value))
        if resolved.kind != "module":
            continue
        out[platform] = reg.create(str(resolved.module_id), **dict(deps or {}))
    return out


def modules_status(
    engines: Mapping[str, str], *, registry: ModuleRegistry | None = None
) -> list[dict[str, object]]:
    """Диагностика для панели/боя: что на модулях, что на адаптерах, чего не хватает."""
    reg = registry or _default_registry
    report: list[dict[str, object]] = []
    for platform, value in (engines or {}).items():
        resolved = resolve_engine(str(value))
        available = resolved.kind != "module" or reg.has(str(resolved.module_id))
        report.append(
            {
                "platform": platform,
                "engine": resolved.raw,
                "kind": resolved.kind,
                "module_id": resolved.module_id,
                "available": available,
            }
        )
    return report
