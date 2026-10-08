"""Реестр нативных provider modules.

Production runtime разрешает только engines.<platform>=module:<id>.
Исторические transport engines физически вынесены в archive/legacy_engines.
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

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

ENGINE_ALIASES: dict[str, str] = {}
KNOWN_ADAPTERS: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedEngine:
    raw: str
    kind: str  # module
    module_id: str | None = None


def resolve_engine(value: str) -> ResolvedEngine:
    """Преобразовать engines.<platform> в решение: модуль или адаптер."""
    raw = str(value or "").strip()
    lowered = raw.lower()
    lowered = ENGINE_ALIASES.get(lowered, lowered)
    if lowered in ("__removed__", "legacy"):
        raise ValueError(
            "legacy engine removed; use module:<id> (e.g. module:youtube, module:telegram)"
        )
    if lowered.startswith("module:"):
        module_id = lowered.split(":", 1)[1].strip()
        if not module_id:
            raise ValueError("engine: пустой id модуля (ожидается module:<id>)")
        return ResolvedEngine(raw=raw, kind="module", module_id=module_id)
    raise ValueError(f"engine: только module:<id> разрешён в HARD_CUT runtime, получено {value!r}")


def _version_gte(current: str, minimum: str) -> bool:
    """Compare semver-ish major.minor.patch (suffix ignored)."""
    import re as _re
    def parts(v: str) -> tuple[int, int, int]:
        core = _re.split(r"[^0-9.]", (v or "").strip())[0]
        bits = (core or "0").split(".")
        out: list[int] = []
        for i in range(3):
            try:
                out.append(int(bits[i]) if i < len(bits) else 0)
            except ValueError:
                out.append(0)
        return out[0], out[1], out[2]
    return parts(current) >= parts(minimum)


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
        mod = factory(**deps)
        # C13: stable ModuleSDK/versioning gate precedes execution.
        try:
            from .module_sdk import ModuleSDK, ModuleCompatibilityError
            ModuleSDK.validate_instance(mod)
        except ModuleCompatibilityError as exc:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                str(exc),
                action="обновите модуль или совместимый ModuleSDK",
            ) from exc
        # F20: refuse load if core < module core_min
        try:
            from .. import __version__ as core_ver
            core_min = str(getattr(getattr(mod, "manifest", None), "core_min", "") or "").strip()
            if core_min and not _version_gte(str(core_ver), core_min):
                raise ModuleError(
                    ModuleErrorCode.FATAL,
                    f"модуль {mid!r} требует core>={core_min}, сейчас {core_ver}",
                    action="обновите orchestrator или понизьте module core_min",
                )
        except ModuleError:
            raise
        except Exception as exc:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                f"не удалось проверить совместимость модуля {mid!r}: {exc}",
                action="проверьте module core_min и версию orchestrator",
            ) from exc
        # Executable capability gate: a manifest cannot advertise a core method
        # that is still inherited from PlatformModule/NotSupported.
        manifest = getattr(mod, "manifest", None)
        strict_contract = bool(getattr(manifest, "extra", {}).get("contract_strict", False))
        if not strict_contract:
            return mod
        cap_to_method = {
            "publish": "publish",
            "schedule_publish": "schedule_publish",
            "update_metadata": "update_metadata",
            "delete": "delete",
        }
        for cap, method_name in cap_to_method.items():
            if not bool(getattr(manifest, "capabilities", {}).get(cap, False)):
                continue
            base_method = getattr(PlatformModule, method_name, None)
            impl_method = getattr(type(mod), method_name, None)
            if base_method is not None and impl_method is base_method:
                raise ModuleError(
                    ModuleErrorCode.FATAL,
                    f"module {mid!r} advertises {cap}=true but does not implement {method_name}()",
                    action="исправьте manifest или реализацию модуля",
                )
        publish_mode = str(getattr(manifest, "publish_mode", "unsupported") or "unsupported")
        publish_cap = bool(getattr(manifest, "capabilities", {}).get("publish", False))
        if publish_mode not in ("unsupported", "partner") and not publish_cap:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                f"module {mid!r} has publish_mode={publish_mode} with publish=false",
                action="синхронизируйте manifest",
            )
        return mod


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

    Все production destinations проходят только через native module registry.
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


# --- регистрация встроенных модулей ---
def _register_builtins() -> None:
    """Импорт встроенных модулей; ошибки импорта — в лог (fail-closed при load)."""
    try:
        from .youtube import create_youtube_module

        register_module("youtube", create_youtube_module)
    except Exception as e:
        # модуль ещё не собран / отсутствует зависимость — fail-closed при load
        logger.warning("модуль youtube не зарегистрирован при старте: %s", e)
    try:
        from .telegram import create_telegram_module

        register_module("telegram", create_telegram_module)
    except Exception as e:
        logger.warning("модуль telegram не зарегистрирован при старте: %s", e)
    try:
        from .instagram import create_instagram_module
        register_module("instagram", create_instagram_module)
    except Exception as e:
        logger.warning("модуль instagram не зарегистрирован при старте: %s", e)
    try:
        from .tiktok import create_tiktok_module
        register_module("tiktok", create_tiktok_module)
    except Exception as e:
        logger.warning("модуль tiktok не зарегистрирован при старте: %s", e)
    try:
        from .facebook import create_facebook_module
        register_module("facebook", create_facebook_module)
    except Exception as e:
        logger.warning("модуль facebook не зарегистрирован при старте: %s", e)
    try:
        from .threads import create_threads_module
        register_module("threads", create_threads_module)
    except Exception as e:
        logger.warning("модуль threads не зарегистрирован при старте: %s", e)

    try:
        from .vk import create_vk_module
        register_module("vk", create_vk_module)
    except Exception as e:
        logger.warning("модуль vk не зарегистрирован при старте: %s", e)
    try:
        from .x import create_x_module
        register_module("x", create_x_module)
    except Exception as e:
        logger.warning("модуль x не зарегистрирован при старте: %s", e)
    try:
        from .rutube import create_rutube_module
        register_module("rutube", create_rutube_module)
    except Exception as e:
        logger.warning("модуль rutube не зарегистрирован при старте: %s", e)


_register_builtins()


# Built-in provider packages. Registration is separate from readiness; manifests and
# contract/access gates determine whether a provider can actually be used for production.
_DISCOVERED_MODULES: tuple[str, ...] = (
    "linkedin", "pinterest", "reddit", "bluesky", "mastodon", "lemmy",
    "farcaster", "nostr", "discord", "slack", "google_business", "dribbble",
    "twitch", "kick", "wordpress", "medium", "devto", "hashnode", "listmonk",
    "mewe", "whop", "skool", "moltbook", "tumblr", "whatsapp", "viber",
    "messenger", "instagram_messaging", "line", "wechat", "signal", "snapchat",
    "beehiiv",
)

def _register_discovered() -> None:
    """Load all registered provider packages; capability/access gates stay in manifests.

    Some modules are fully native, some partial, and some intentionally scaffold/feasibility
    gated. Registration itself must not imply production readiness.
    """
    for _mid in _DISCOVERED_MODULES:
        try:
            mod = __import__(f"orchestrator.platforms.{_mid}.module", fromlist=["create_module"])
            register_module(_mid, getattr(mod, "create_module"))
        except Exception as exc:
            logger.warning("planned module %s not registered: %s", _mid, exc)


_register_discovered()
