"""Postiz-адаптер: PlatformModule поверх существующего PostizClient.

См. engines/postiz_engine.py (старый слой) и docs/dev/02_MODULE_STANDARD.txt.
P4: unit + dry-run; в прод engines не переключаем до P5.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from ..base import (
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
from ..manifest import ModuleManifest, load_manifest

logger = logging.getLogger(__name__)

_MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")


class _PostizClientProto(Protocol):
    def upload_media(self, path: str, platform: str) -> Any: ...
    def create_post(
        self,
        platform: str,
        media: Any,
        content: dict[str, Any],
        scheduled_for: datetime | None = None,
    ) -> Any: ...
    def delete_post(self, post_id: str) -> None: ...
    def get_post(self, post_id: str) -> Any: ...


class _DryRunClient:
    """Минимальный mock Postiz для dry-run без сети."""

    def __init__(self, platform: str = "youtube") -> None:
        self.platform = platform
        self._n = 0

    def upload_media(self, path: str, platform: str) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(id=f"media-dry-{path}", path=path or "")

    def create_post(
        self,
        platform: str,
        media: Any,
        content: dict[str, Any],
        scheduled_for: datetime | None = None,
    ) -> Any:
        from types import SimpleNamespace

        self._n += 1
        pid = f"postiz-dry-{self._n}"
        state = "scheduled" if scheduled_for else "published"
        return SimpleNamespace(
            id=pid,
            platform=platform,
            scheduled_for=scheduled_for,
            status=state,
            release_url=f"https://example.invalid/{pid}",
            content=content,
            error=None,
        )

    def delete_post(self, post_id: str) -> None:
        return None

    def get_post(self, post_id: str) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(
            id=post_id,
            platform=self.platform,
            scheduled_for=None,
            status="published",
            release_url=f"https://example.invalid/{post_id}",
            content=None,
            error=None,
        )


def _map_postiz_exc(e: Exception) -> ModuleError:
    msg = str(e)[:300]
    low = msg.lower()
    if "401" in low or "unauthorized" in low or "token" in low and "invalid" in low:
        return ModuleError(
            ModuleErrorCode.AUTH_REQUIRED,
            f"Postiz: требуется авторизация. {msg}",
            action="проверьте POSTIZ_API_TOKEN в .env",
        )
    if "429" in low or "rate" in low:
        return ModuleError(
            ModuleErrorCode.RATE_LIMIT,
            f"Postiz: лимит запросов. {msg}",
            action="backoff / Retry-After",
            retryable=True,
        )
    if "integration" in low:
        return ModuleError(
            ModuleErrorCode.FATAL,
            f"Postiz: нет integration_id. {msg}",
            action="задайте platforms.<p>.integration_id",
        )
    if "timeout" in low or "connect" in low or "network" in low:
        return ModuleError(
            ModuleErrorCode.TRANSIENT,
            f"Postiz: сеть. {msg}",
            action="повторить",
            retryable=True,
        )
    return ModuleError(
        ModuleErrorCode.PLATFORM_REJECTED,
        f"Postiz отклонил операцию. {msg}",
        action="см. уведомления Postiz / логи",
    )


class PostizModule(PlatformModule):
    """Адаптер одной платформы через Postiz API."""

    def __init__(
        self,
        client: _PostizClientProto | None,
        *,
        platform: str = "youtube",
        integration_id: str = "",
        dry_run: bool = False,
        account_label: str = "",
    ) -> None:
        self.manifest: ModuleManifest = load_manifest(_MANIFEST_PATH)
        self._platform = (platform or "youtube").strip().lower()
        self._integration_id = (integration_id or "").strip()
        self._dry_run = bool(dry_run)
        self._account_label = account_label or f"postiz:{self._platform}"
        if dry_run or client is None:
            self._client: _PostizClientProto = _DryRunClient(self._platform)
        else:
            self._client = client

    def auth_status(self) -> AuthStatus:
        token = (os.getenv("POSTIZ_API_TOKEN") or "").strip()
        if self._dry_run:
            return AuthStatus(ok=True, account=self._account_label, details="dry-run")
        if not token:
            return AuthStatus(
                ok=False,
                account=self._account_label,
                details="POSTIZ_API_TOKEN не задан",
            )
        # лёгкая проверка без лишних вызовов — list_scheduled если есть
        try:
            list_fn = getattr(self._client, "list_scheduled", None)
            if callable(list_fn):
                list_fn(self._platform)
            return AuthStatus(ok=True, account=self._account_label, details="token present")
        except Exception as e:
            return AuthStatus(
                ok=False,
                account=self._account_label,
                details=str(e)[:200],
            )

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        if not self._dry_run and not (os.getenv("POSTIZ_API_TOKEN") or "").strip():
            errs.append("POSTIZ_API_TOKEN пуст")
        if not self._integration_id and not self._dry_run:
            # не блокер unit — runtime create_post упадёт с понятной ошибкой
            pass
        return errs

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path, kind=media.kind)

    def _content_from_meta(self, meta: PublishMeta) -> dict[str, Any]:
        extra = dict(meta.extra or {})
        content: dict[str, Any] = {
            "title": meta.title or "",
            "description": meta.description or "",
            "hashtags": meta.hashtags or "",
        }
        if self._integration_id:
            content["integration_id"] = self._integration_id
        # пробрасываем известные ключи из extra
        for k in ("integration_id", "integrationId", "settings", "group", "post_type"):
            if k in extra and extra[k] is not None:
                content[k] = extra[k]
        return content

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        content = self._content_from_meta(meta)
        media_ref: Any = None
        try:
            if media.path and Path(media.path).is_file():
                media_ref = self._client.upload_media(media.path, self._platform)
            post = self._client.create_post(
                self._platform, media_ref, content, scheduled_for=None
            )
        except ModuleError:
            raise
        except Exception as e:
            raise _map_postiz_exc(e) from e

        pid = str(getattr(post, "id", "") or "")
        if not pid:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                "Postiz не вернул id поста",
                action="проверьте ответ create_post",
            )
        url = str(getattr(post, "release_url", "") or "")
        state = str(getattr(post, "status", "published") or "published")
        return PublishResult(external_id=pid, url=url, state=state)

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        # Postiz schedule задаётся при create_post; отдельного reschedule в клиенте нет
        raise NotSupported("schedule_publish")

    def upload(
        self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None
    ) -> UploadResult:
        """Загрузка + отложенная публикация через create_post(scheduled_for=when)."""
        content = self._content_from_meta(meta)
        if when is not None:
            content["post_type"] = content.get("post_type") or "schedule"
        media_ref: Any = None
        try:
            if media.path and Path(media.path).is_file():
                media_ref = self._client.upload_media(media.path, self._platform)
            post = self._client.create_post(
                self._platform, media_ref, content, scheduled_for=when
            )
        except ModuleError:
            raise
        except Exception as e:
            raise _map_postiz_exc(e) from e
        pid = str(getattr(post, "id", "") or "")
        url = str(getattr(post, "release_url", "") or "")
        state = "scheduled" if when else "uploaded"
        return UploadResult(external_id=pid, url=url, state=state)

    def delete(self, external_id: str) -> bool:
        try:
            self._client.delete_post(str(external_id))
            return True
        except Exception as e:
            logger.warning("postiz delete %s: %s", external_id, e)
            raise _map_postiz_exc(e) from e

    def get_status(self, external_id: str) -> PublishStatus:
        try:
            post = self._client.get_post(str(external_id))
        except Exception as e:
            return PublishStatus(state="failed", error=str(e)[:200])
        if post is None:
            return PublishStatus(state="failed", error="пост не найден")
        status = str(getattr(post, "status", "") or "unknown").lower()
        url = str(getattr(post, "release_url", "") or "")
        err = str(getattr(post, "error", "") or "")
        if status in ("error", "failed"):
            return PublishStatus(state="failed", url=url, error=err)
        if status in ("queue", "scheduled", "processing", "pending"):
            return PublishStatus(state="processing", url=url)
        if status in ("published", "done", "completed", "success"):
            return PublishStatus(state="published", url=url)
        return PublishStatus(state=status or "unknown", url=url, error=err)

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        raise NotSupported("update_metadata")

    def check_claims(self, external_id: str) -> ClaimsResult:
        return ClaimsResult(supported=False, status="unknown")


def create_postiz_module(
    *,
    client: Any = None,
    platform: str = "youtube",
    integration_id: str = "",
    dry_run: bool = False,
    account_label: str = "",
    **_kwargs: Any,
) -> PostizModule:
    return PostizModule(
        client,
        platform=platform,
        integration_id=integration_id,
        dry_run=dry_run,
        account_label=account_label,
    )
