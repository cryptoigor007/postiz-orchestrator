"""Модуль Telegram: реализация PlatformModule.

См. docs/modules/MODULE_TELEGRAM.txt.
Основной сценарий: ссылочный пост (title + description + кнопка на YouTube).
at_slot only; early_upload/schedule_publish не поддерживаются.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ...http_client import ModuleHttpClient
from ..base import (
    RemotePage,
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
from .api import MAX_TEXT, TelegramApi

logger = logging.getLogger(__name__)

_MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")
BOT_ID_PREFIX = "tg:"


def _message_id_of(external_id: str) -> int | None:
    s = str(external_id or "")
    if s.startswith(BOT_ID_PREFIX):
        s = s[len(BOT_ID_PREFIX) :]
    try:
        return int(s)
    except ValueError:
        return None


def _build_link_text(meta: PublishMeta) -> tuple[str, str | None, dict[str, Any] | None]:
    """Собрать HTML-текст + preview url + inline keyboard для link-поста."""
    extra = meta.extra or {}
    title = (meta.title or "").strip()
    desc = (meta.description or "").strip()
    link = str(extra.get("link") or extra.get("youtube_url") or extra.get("url") or "").strip()
    button_text = str(extra.get("button_text") or "▶ Смотреть").strip() or "▶ Смотреть"

    parts: list[str] = []
    if title:
        # экранируем HTML
        safe_title = (
            title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        parts.append(f"<b>{safe_title}</b>")
    if desc:
        safe_desc = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(safe_desc)
    if link and link not in desc and link not in title:
        parts.append(link)

    text = "\n\n".join(parts).strip() or (link or " ")
    text = text[:MAX_TEXT]

    reply_markup = None
    if link:
        reply_markup = {
            "inline_keyboard": [[{"text": button_text, "url": link}]]
        }
    preview_url = link or None
    return text, preview_url, reply_markup


def _release_url(chat: dict[str, Any] | None, message_id: int) -> str:
    """t.me/<username>/<message_id> для публичного канала."""
    if not chat or not message_id:
        return ""
    username = (chat.get("username") or "").strip()
    if username:
        return f"https://t.me/{username}/{message_id}"
    return ""


class TelegramModule(PlatformModule):
    """Прямой модуль Telegram Bot API (at_slot, link + media)."""

    def __init__(
        self,
        token: str,
        chat_id: str | int,
        *,
        http: ModuleHttpClient | None = None,
        parse_mode: str = "HTML",
        show_above: bool = True,
        disable_notification: bool = False,
        max_video_mb: int = 50,
        dry_run: bool = False,
        account_label: str = "",
        post_mode: str = "link",  # link | media
    ) -> None:
        self.manifest: ModuleManifest = load_manifest(_MANIFEST_PATH)
        self._token = (token or "").strip()
        self._chat_id = chat_id
        self._dry_run = bool(dry_run)
        self._account_label = account_label or ""
        self._post_mode = (post_mode or "link").lower()
        self._api = TelegramApi(
            self._token,
            chat_id,
            http=http,
            parse_mode=parse_mode,
            show_above=show_above,
            disable_notification=disable_notification,
            max_video_mb=max_video_mb,
            dry_run=dry_run,
        )
        self._chat_cache: dict[str, Any] | None = None

    def auth_status(self) -> AuthStatus:
        if not self._token:
            return AuthStatus(
                ok=False,
                account=self._account_label,
                details="TELEGRAM_BOT_TOKEN не задан",
            )
        if not self._chat_id:
            return AuthStatus(
                ok=False,
                account=self._account_label,
                details="publish_chat_id не задан",
            )
        try:
            me = self._api.get_me()
            username = me.get("username") or str(me.get("id") or "")
            # optionally verify chat
            try:
                chat = self._api.get_chat()
                self._chat_cache = chat
            except ModuleError:
                chat = None
            label = self._account_label or (f"@{username}" if username else "")
            return AuthStatus(
                ok=True,
                account=label,
                details="bot ok" + (f"; chat={chat.get('type')}" if chat else ""),
            )
        except ModuleError as e:
            return AuthStatus(
                ok=False,
                account=self._account_label,
                details=e.message,
            )
        except Exception as e:
            return AuthStatus(
                ok=False,
                account=self._account_label,
                details=str(e)[:200],
            )

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        if not self._token:
            errs.append("TELEGRAM_BOT_TOKEN пуст")
        if not self._chat_id:
            errs.append("platforms.telegram.publish_chat_id пуст")
        return errs

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        notes: list[str] = []
        if media.kind == "video" and media.path:
            p = Path(media.path)
            if p.is_file():
                mb = p.stat().st_size / (1024 * 1024)
                if mb > self._api.max_video_mb:
                    notes.append(
                        f"видео {mb:.1f} МБ > {self._api.max_video_mb} МБ — "
                        "рекомендуется post_mode=link"
                    )
        return PreparedMedia(path=media.path, kind=media.kind, notes=notes)

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        """at_slot: sendMessage (link) или sendVideo/sendPhoto (media)."""
        mode = self._post_mode
        extra = meta.extra or {}
        if extra.get("post_mode"):
            mode = str(extra["post_mode"]).lower()

        if mode == "media" and media.path and Path(media.path).is_file():
            if media.kind == "image":
                text, preview, markup = _build_link_text(meta)
                caption = text[:1024]
                res = self._api.send_photo(
                    media.path, caption=caption, reply_markup=markup
                )
            else:
                text, preview, markup = _build_link_text(meta)
                caption = text[:1024]
                res = self._api.send_video(
                    media.path, caption=caption, reply_markup=markup
                )
        else:
            # link (default) — основной сценарий проекта
            text, preview, markup = _build_link_text(meta)
            res = self._api.send_message(
                text, reply_markup=markup, link_preview_url=preview
            )

        mid = res.get("message_id")
        if mid is None:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                "Bot API не вернул message_id",
                action="проверьте ответ send*",
            )
        external_id = f"{BOT_ID_PREFIX}{mid}"
        chat = res.get("chat") if isinstance(res.get("chat"), dict) else self._chat_cache
        if not chat:
            try:
                chat = self._api.get_chat()
                self._chat_cache = chat
            except Exception:
                chat = None
        url = _release_url(chat, int(mid))
        return PublishResult(external_id=external_id, url=url, state="published")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        mid = _message_id_of(external_id)
        if mid is None:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                f"некорректный external_id: {external_id!r}",
                action="ожидается tg:<message_id>",
            )
        text, preview, markup = _build_link_text(patch)
        self._api.edit_message_text(
            mid, text, reply_markup=markup, link_preview_url=preview
        )
        return True

    def update_media(self, external_id: str, *, media_type: str, media: str, caption: str = "") -> bool:
        mid=_message_id_of(external_id)
        if mid is None: raise ModuleError(ModuleErrorCode.FATAL,"некорректный external_id")
        self._api.edit_message_media(mid,media_type=media_type,media=media,caption=caption)
        return True

    def delete(self, external_id: str) -> bool:
        mid = _message_id_of(external_id)
        if mid is None:
            return False
        return self._api.delete_message(mid)

    def get_status(self, external_id: str) -> PublishStatus:
        mid = _message_id_of(external_id)
        if mid is None:
            return PublishStatus(state="failed", error="некорректный external_id")
        # Bot API не даёт getMessage; считаем published если id валиден
        chat = self._chat_cache
        url = _release_url(chat, mid) if chat else ""
        return PublishStatus(state="published", url=url)

    def check_claims(self, external_id: str) -> ClaimsResult:
        return ClaimsResult(supported=False, status="unknown", details="Telegram не отдаёт клеймы")


    def list_remote_items(self, **kwargs):  # noqa: ANN003
        """Bot API does not expose channel history inventory."""
        raise NotSupported("list_remote_items")

    def upload(self, media: PreparedMedia, meta: PublishMeta, when: datetime | None = None) -> UploadResult:
        raise NotSupported("upload")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        raise NotSupported("schedule_publish")


def create_telegram_module(
    *,
    token: str | None = None,
    chat_id: str | int | None = None,
    http: ModuleHttpClient | None = None,
    dry_run: bool = False,
    account_label: str = "",
    parse_mode: str = "HTML",
    show_above: bool = True,
    disable_notification: bool = False,
    max_video_mb: int = 50,
    post_mode: str = "link",
    **_kwargs: Any,
) -> TelegramModule:
    """Фабрика для registry. Токен по умолчанию из env."""
    tok = (token if token is not None else os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
    cid = chat_id if chat_id is not None else os.getenv("TELEGRAM_PUBLISH_CHAT_ID", "")
    return TelegramModule(
        tok,
        cid or "",
        http=http,
        dry_run=dry_run,
        account_label=account_label,
        parse_mode=parse_mode,
        show_above=show_above,
        disable_notification=disable_notification,
        max_video_mb=max_video_mb,
        post_mode=post_mode,
    )
