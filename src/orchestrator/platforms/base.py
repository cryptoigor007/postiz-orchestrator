"""Базовый контракт платформенных модулей.

См. docs/dev/02_MODULE_STANDARD.txt — контракт PlatformModule, таксономия ошибок
и типы данных. Ядро общается с платформами ТОЛЬКО через этот интерфейс.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ModuleErrorCode(StrEnum):
    """Единая таксономия ошибок (02_MODULE_STANDARD §4)."""

    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    QUOTA = "QUOTA"
    RATE_LIMIT = "RATE_LIMIT"
    MEDIA_INVALID = "MEDIA_INVALID"
    PLATFORM_REJECTED = "PLATFORM_REJECTED"
    CLAIM_BLOCKED = "CLAIM_BLOCKED"
    TRANSIENT = "TRANSIENT"
    FATAL = "FATAL"


_RETRYABLE_BY_DEFAULT: frozenset[ModuleErrorCode] = frozenset(
    {ModuleErrorCode.TRANSIENT, ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.AUTH_EXPIRED}
)


class ModuleError(Exception):
    """Ошибка модуля с кодом таксономии, действием и признаком retry."""

    def __init__(
        self,
        code: ModuleErrorCode | str,
        message: str,
        *,
        action: str = "",
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.code = ModuleErrorCode(code)
        self.message = str(message)
        self.action = action
        self.retryable = (
            self.code in _RETRYABLE_BY_DEFAULT if retryable is None else bool(retryable)
        )


class NotSupported(Exception):
    """Метод не поддерживается платформой (см. capabilities в манифесте)."""

    def __init__(self, method: str) -> None:
        super().__init__(f"{method}: не поддерживается платформой")
        self.method = method


@dataclass
class AuthStatus:
    ok: bool
    account: str = ""
    expires_at: str | None = None
    scopes: list[str] = field(default_factory=list)
    details: str = ""


@dataclass
class MediaSpec:
    path: str
    kind: str = "video"  # video | image | text
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreparedMedia:
    path: str
    kind: str = "video"
    notes: list[str] = field(default_factory=list)


@dataclass
class PublishMeta:
    title: str = ""
    description: str = ""
    hashtags: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class UploadResult:
    external_id: str
    url: str = ""
    state: str = "uploaded"  # uploaded | hidden | scheduled


@dataclass
class PublishResult:
    external_id: str
    url: str = ""
    state: str = "published"


@dataclass
class PublishStatus:
    state: str  # uploaded | processing | published | blocked | failed | deleted
    url: str = ""
    error: str = ""


@dataclass
class ClaimsResult:
    supported: bool = False
    status: str = "unknown"  # none | claimed | unknown
    details: str = ""


class PlatformModule(ABC):
    """Контракт платформенного модуля (02_MODULE_STANDARD §4).

    Обязательны: манифест и auth_status(). Остальное — по capabilities манифеста;
    неподдерживаемые методы поднимают NotSupported.
    """

    manifest: Any  # ModuleManifest (импортируется из .manifest — без цикла)

    # ---- обязательное ----
    @abstractmethod
    def auth_status(self) -> AuthStatus: ...

    # ---- по желанию (переопределяются модулями) ----
    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        return []

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path, kind=media.kind)

    def upload(
        self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None
    ) -> UploadResult:
        raise NotSupported("upload")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        raise NotSupported("schedule_publish")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        raise NotSupported("publish")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        raise NotSupported("update_metadata")

    def delete(self, external_id: str) -> bool:
        raise NotSupported("delete")

    def get_status(self, external_id: str) -> PublishStatus:
        raise NotSupported("get_status")

    def check_claims(self, external_id: str) -> ClaimsResult:
        """По умолчанию: платформа клеймы через API не отдаёт (ручной чекпойнт ядра)."""
        return ClaimsResult()

    def capabilities(self) -> dict[str, bool]:
        return dict(getattr(self.manifest, "capabilities", {}) or {})
