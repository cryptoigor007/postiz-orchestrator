"""Манифест платформенного модуля: чтение и валидация manifest.yaml.

Схема полей — docs/dev/02_MODULE_STANDARD.txt §3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..yaml_utils import DuplicateYAMLKeyError, load_unique_yaml

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
    "clips",
    "public_media_required",
    "list_uploads",
    "list_scheduled",
    "list_private",
    "messages",
    "webhooks",
)

ENUM_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "scan_mode": ("auto", "published_only", "unsupported", "manual"),
    "schedule_owner": ("platform", "orchestrator"),
}


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
    publish_mode: str = "unsupported"
    status_authority: str = "unknown"
    media_transfer: str = "mixed"
    review_requirement: str = "none"
    account_types: list[str] = field(default_factory=list)
    messaging: dict[str, Any] = field(default_factory=dict)
    webhooks: dict[str, Any] = field(default_factory=dict)
    provider_type: str = ""
    sdk_min: str = "1.0.0"
    sdk_policy: str = "backward_compatible"
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
        unknown = sorted(set(caps) - set(BOOL_CAPABILITIES) - {"claims_check", "content_kinds", "content_kind_default"} - set(ENUM_CAPABILITIES))
        if unknown:
            raise ManifestError(f"manifest: неизвестные capabilities: {', '.join(unknown)}")
        for key, value in caps.items():
            if key in ("claims_check", "content_kinds", "content_kind_default"):
                continue
            if key in ENUM_CAPABILITIES:
                allowed = ENUM_CAPABILITIES[key]
                if str(value).lower() not in allowed:
                    raise ManifestError(
                        f"manifest: capabilities.{key} должен быть {'|'.join(allowed)}"
                    )
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

        for field_name, allowed in {
            "publish_mode": ("direct", "orchestrator", "inbox", "manual", "partner", "unsupported"),
            "status_authority": ("authoritative", "best_effort", "unknown"),
            "media_transfer": ("file_upload", "resumable", "pull_from_url", "container", "mixed"),
            "review_requirement": ("none", "app_review", "audit", "business_verification", "partner", "development_then_standard", "trial_then_standard", "project_access_approval", "registration_required"),
        }.items():
            value = str(data.get(field_name, {"publish_mode":"unsupported","status_authority":"unknown","media_transfer":"mixed","review_requirement":"none"}[field_name])).lower()
            if value not in allowed:
                raise ManifestError(f"manifest: {field_name} должен быть {'|'.join(allowed)}")
        sdk_min = str(data.get("sdk_min") or "1.0.0")
        sdk_policy_raw = data.get("sdk_policy")
        sdk_policy = str(sdk_policy_raw or "backward_compatible").lower() if not isinstance(sdk_policy_raw, dict) else "backward_compatible"
        account_types = data.get("account_types") or []
        if not isinstance(account_types, list) or not all(isinstance(x, str) and x.strip() for x in account_types):
            raise ManifestError("manifest: account_types должен быть списком строк")

        docs = str(data.get("docs") or "").strip()
        if not docs:
            raise ManifestError("manifest: docs обязателен (имя файла ТЗ)")

        module_id = str(data.get("id") or "").strip().lower()
        if not module_id:
            raise ManifestError("manifest: id обязателен")

        known = set(REQUIRED_KEYS) | {
            "description", "publish_mode", "status_authority", "media_transfer",
            "review_requirement", "account_types", "messaging", "webhooks",
            "version_policy", "sdk_policy", "provider_type", "sdk_min",
        }
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
            publish_mode=str(data.get("publish_mode") or "unsupported"),
            status_authority=str(data.get("status_authority") or "unknown"),
            media_transfer=str(data.get("media_transfer") or "mixed"),
            review_requirement=str(data.get("review_requirement") or "none"),
            account_types=list(account_types),
            messaging=dict(data.get("messaging") or {}),
            webhooks=dict(data.get("webhooks") or {}),
            provider_type=str(data.get("provider_type") or ""),
            sdk_min=sdk_min,
            sdk_policy=sdk_policy,
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
        data = load_unique_yaml(p) or {}
    except DuplicateYAMLKeyError as exc:
        raise ManifestError(f"manifest: duplicate YAML key: {exc}") from exc
    except yaml.YAMLError as exc:  # pragma: no cover - редкий случай
        raise ManifestError(f"manifest: не удалось прочитать YAML: {exc}") from exc
    return ModuleManifest.from_dict(data)
