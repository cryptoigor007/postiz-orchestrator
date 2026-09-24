"""Манифест платформенного модуля: чтение и валидация manifest.yaml.

Схема полей — docs/dev/02_MODULE_STANDARD.txt §3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REQUIRED_KEYS: tuple[str, ...] = (
    "id",
    "name",
    "api_version",
    "module_version",
    "core_min",
    "auth",
    "capabilities",
    "limits",
    "media",
    "statuses",
    "docs",
)

BOOL_CAPABILITIES: tuple[str, ...] = (
    "publish",
    "early_upload",
    "schedule_publish",
    "update_metadata",
    "delete",
    "thumbnail",
    "video",
    "image",
    "text",
    "stories",
    "public_media_required",
)

CLAIMS_VALUES: tuple[str, ...] = ("auto", "manual", "unsupported")


class ManifestError(ValueError):
    """Манифест отсутствует, неполный или некорректен."""


@dataclass
class ModuleManifest:
    id: str
    name: str
    api_version: str
    module_version: str
    core_min: str
    auth: dict[str, Any]
    capabilities: dict[str, Any]
    limits: dict[str, Any]
    media: dict[str, Any]
    statuses: dict[str, Any]
    docs: str
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModuleManifest:
        if not isinstance(data, dict):
            raise ManifestError("manifest: ожидается словарь (YAML mapping)")

        missing = [key for key in REQUIRED_KEYS if key not in data]
        if missing:
            raise ManifestError(f"manifest: отсутствуют обязательные поля: {', '.join(missing)}")

        caps = data.get("capabilities")
        if not isinstance(caps, dict):
            raise ManifestError("manifest: capabilities должен быть словарём")
        unknown = sorted(set(caps) - set(BOOL_CAPABILITIES) - {"claims_check"})
        if unknown:
            raise ManifestError(f"manifest: неизвестные capabilities: {', '.join(unknown)}")
        for key, value in caps.items():
            if key == "claims_check":
                continue
            if not isinstance(value, bool):
                raise ManifestError(f"manifest: capabilities.{key} должен быть true/false")

        claims = str(caps.get("claims_check", "unsupported")).lower()
        if claims not in CLAIMS_VALUES:
            raise ManifestError(
                f"manifest: capabilities.claims_check должен быть {'|'.join(CLAIMS_VALUES)}"
            )

        auth = data.get("auth")
        if not isinstance(auth, dict) or not auth.get("method"):
            raise ManifestError("manifest: auth.method обязателен")

        docs = str(data.get("docs") or "").strip()
        if not docs:
            raise ManifestError("manifest: docs обязателен (имя файла ТЗ)")

        module_id = str(data.get("id") or "").strip().lower()
        if not module_id:
            raise ManifestError("manifest: id обязателен")

        known = set(REQUIRED_KEYS) | {"description"}
        return cls(
            id=module_id,
            name=str(data.get("name") or module_id),
            api_version=str(data.get("api_version") or ""),
            module_version=str(data.get("module_version") or ""),
            core_min=str(data.get("core_min") or ""),
            auth=dict(auth),
            capabilities=dict(caps),
            limits=dict(data.get("limits") or {}),
            media=dict(data.get("media") or {}),
            statuses=dict(data.get("statuses") or {}),
            docs=docs,
            extra={k: v for k, v in data.items() if k not in known},
        )

    def claims_check(self) -> str:
        return str(self.capabilities.get("claims_check", "unsupported")).lower()

    def capability(self, name: str) -> bool:
        return bool(self.capabilities.get(name, False))


def load_manifest(path: str | Path) -> ModuleManifest:
    p = Path(path)
    if not p.is_file():
        raise ManifestError(f"manifest: файл не найден: {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - редкий случай
        raise ManifestError(f"manifest: не удалось прочитать YAML: {exc}") from exc
    return ModuleManifest.from_dict(data)
