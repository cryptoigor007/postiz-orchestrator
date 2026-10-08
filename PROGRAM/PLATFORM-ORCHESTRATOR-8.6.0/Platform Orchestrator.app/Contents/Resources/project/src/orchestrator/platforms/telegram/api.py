"""Низкоуровневый клиент Telegram Bot API для модуля.

Использует ModuleHttpClient ядра (таймауты, backoff, Retry-After, mask ***).
См. docs/modules/MODULE_TELEGRAM.txt §2, §10.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from ...http_client import ModuleHttpClient, mask_secrets
from ..base import ModuleError, ModuleErrorCode
from ..errors import message_for

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
MAX_TEXT = 4096
MAX_CAPTION = 1024
MAX_VIDEO_MB = 50
MAX_PHOTO_MB = 10


def _map_telegram_error(status: int, body: str, method: str) -> ModuleError:
    """Маппинг HTTP/описания Bot API → ModuleErrorCode + RU текст."""
    text = (body or "").lower()
    detail = mask_secrets((body or "")[:300])

    if status == 401 or "unauthorized" in text:
        msg, action = message_for(ModuleErrorCode.AUTH_REQUIRED, detail)
        return ModuleError(ModuleErrorCode.AUTH_REQUIRED, msg, action=action)

    if status == 403 or "forbidden" in text or "bot was blocked" in text or "kicked" in text:
        code = ModuleErrorCode.PLATFORM_REJECTED
        if "not enough rights" in text or "chat_admin_required" in text:
            msg, action = message_for(
                code,
                "боту не хватает прав в канале (нужна публикация/редактирование сообщений).",
            )
        else:
            msg, action = message_for(code, detail or "доступ запрещён.")
        return ModuleError(
            code, msg, action=action or "проверьте права бота в канале"
        )

    if status == 429 or "too many requests" in text or "retry_after" in text:
        msg, action = message_for(ModuleErrorCode.RATE_LIMIT, detail)
        return ModuleError(ModuleErrorCode.RATE_LIMIT, msg, action=action, retryable=True)

    if status == 400:
        if "message is too long" in text or "caption is too long" in text:
            msg, action = message_for(
                ModuleErrorCode.MEDIA_INVALID,
                "текст/подпись слишком длинные (лимит 4096/1024).",
            )
            return ModuleError(ModuleErrorCode.MEDIA_INVALID, msg, action=action)
        if "file too big" in text or "too large" in text or "entity too large" in text:
            msg, action = message_for(
                ModuleErrorCode.MEDIA_INVALID,
                f"файл превышает лимит Bot API (видео ≤{MAX_VIDEO_MB} МБ, фото ≤{MAX_PHOTO_MB} МБ).",
            )
            return ModuleError(ModuleErrorCode.MEDIA_INVALID, msg, action=action)
        if "chat not found" in text or "chat_id is empty" in text:
            msg, action = message_for(
                ModuleErrorCode.PLATFORM_REJECTED,
                "chat_id не найден или пуст — проверьте publish_chat_id.",
            )
            return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, msg, action=action)
        if "parse entities" in text:
            msg, action = message_for(
                ModuleErrorCode.PLATFORM_REJECTED,
                "не удалось разобрать HTML-разметку.",
            )
            return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, msg, action=action)
        msg, action = message_for(ModuleErrorCode.PLATFORM_REJECTED, detail)
        return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, msg, action=action)

    if status >= 500:
        msg, action = message_for(ModuleErrorCode.TRANSIENT, f"HTTP {status}")
        return ModuleError(ModuleErrorCode.TRANSIENT, msg, action=action, retryable=True)

    msg, action = message_for(
        ModuleErrorCode.FATAL, f"{method} HTTP {status}: {detail}"
    )
    return ModuleError(ModuleErrorCode.FATAL, msg, action=action)


class TelegramApi:
    """Клиент Bot API: sendMessage / sendVideo / sendPhoto / edit / delete / getMe / getChat."""

    def __init__(
        self,
        token: str,
        chat_id: str | int,
        *,
        http: ModuleHttpClient | None = None,
        parse_mode: str = "HTML",
        show_above: bool = True,
        disable_notification: bool = False,
        max_video_mb: int = MAX_VIDEO_MB,
        dry_run: bool = False,
    ) -> None:
        self.token = (token or "").strip()
        self.chat_id = chat_id
        self.parse_mode = parse_mode or "HTML"
        self.show_above = bool(show_above)
        self.disable_notification = bool(disable_notification)
        self.max_video_mb = int(max_video_mb) if max_video_mb else MAX_VIDEO_MB
        self.dry_run = bool(dry_run)
        self._http = http or ModuleHttpClient(
            platform="telegram", module_version="1.0.0", read_timeout=30.0, max_retries=3
        )
        self._base = f"{API_BASE}/bot{self.token}" if self.token else ""

    @property
    def enabled(self) -> bool:
        return bool(self.token) and bool(self.chat_id)

    def _url(self, method: str) -> str:
        if not self.token:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                "TELEGRAM_BOT_TOKEN не задан.",
                action="задайте токен бота в .env (chmod 600).",
            )
        return f"{self._base}/{method}"

    def _call_json(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.dry_run:
            logger.info("telegram dry-run %s chat_id=%s", method, self.chat_id)
            if method.startswith("send"):
                return {
                    "message_id": 900001,
                    "chat": {"id": self.chat_id, "username": "dry_run_channel"},
                }
            if method.startswith("edit"):
                return {"message_id": payload.get("message_id", 0)}
            if method == "deleteMessage":
                return {}
            if method == "getMe":
                return {"id": 1, "is_bot": True, "username": "dry_run_bot"}
            if method == "getChat":
                return {
                    "id": self.chat_id,
                    "type": "channel",
                    "username": "dry_run_channel",
                }
            return {}

        url = self._url(method)
        try:
            resp = self._http.request("POST", url, json=payload)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise ModuleError(
                ModuleErrorCode.TRANSIENT,
                f"сеть/транспорт Bot API: {mask_secrets(str(e))[:200]}",
                action="повторить с backoff",
                retryable=True,
            ) from e

        body_text = resp.text or ""
        try:
            data = resp.json() if resp.content else {}
        except Exception:
            data = {}

        if resp.status_code >= 400:
            desc = ""
            if isinstance(data, dict):
                desc = str(data.get("description") or data.get("error") or body_text)
            else:
                desc = body_text
            raise _map_telegram_error(resp.status_code, desc, method)

        if not isinstance(data, dict):
            raise ModuleError(
                ModuleErrorCode.FATAL,
                f"неожиданный ответ {method}: не dict",
                action="проверьте логи http",
            )
        if not data.get("ok", True) and "result" not in data:
            # некоторые ответы ok=false
            desc = str(data.get("description") or data)
            raise _map_telegram_error(400, desc, method)

        result = data.get("result", data)
        if isinstance(result, dict):
            return result
        if result is True or result is False:
            return {"ok": result}
        return data if isinstance(data, dict) else {}

    def get_me(self) -> dict[str, Any]:
        return self._call_json("getMe", {})

    def get_chat(self) -> dict[str, Any]:
        return self._call_json("getChat", {"chat_id": self.chat_id})

    def send_message(
        self,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        link_preview_url: str | None = None,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        text = (text or "")[:MAX_TEXT]
        if not text.strip():
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                "пустой текст сообщения.",
                action="передайте title/description или link.",
            )
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_notification": self.disable_notification,
        }
        pm = parse_mode if parse_mode is not None else self.parse_mode
        if pm:
            payload["parse_mode"] = pm
        preview: dict[str, Any] = {"is_disabled": False}
        if self.show_above:
            preview["show_above_text"] = True
        if link_preview_url:
            preview["url"] = link_preview_url
        payload["link_preview_options"] = preview
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            return self._call_json("sendMessage", payload)
        except ModuleError as e:
            if (
                e.code == ModuleErrorCode.PLATFORM_REJECTED
                and "html" in (e.message or "").lower()
            ):
                logger.warning("telegram HTML не разобрался, отправляю plain text")
                payload.pop("parse_mode", None)
                return self._call_json("sendMessage", payload)
            raise

    def send_video(
        self,
        path: str | Path,
        *,
        caption: str = "",
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        p = Path(path)
        if not p.is_file():
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                f"видеофайл не найден: {p}",
                action="проверьте путь к медиа.",
            )
        size_mb = p.stat().st_size / (1024 * 1024)
        if size_mb > self.max_video_mb:
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                f"видео {size_mb:.1f} МБ > лимита Bot API {self.max_video_mb} МБ.",
                action="используйте ссылочный пост (link) или уменьшите файл.",
            )
        if self.dry_run:
            return self._call_json(
                "sendVideo",
                {"chat_id": self.chat_id, "caption": (caption or "")[:MAX_CAPTION]},
            )
        # multipart через общий ModuleHttpClient, чтобы таймауты/маскирование/transport
        # были единообразными для всех provider uploads.
        url = self._url("sendVideo")
        data: dict[str, Any] = {
            "chat_id": str(self.chat_id),
            "caption": (caption or "")[:MAX_CAPTION],
            "disable_notification": str(self.disable_notification).lower(),
        }
        if self.parse_mode:
            data["parse_mode"] = self.parse_mode
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        try:
            with open(p, "rb") as fh:
                resp = self._http.request(
                    "POST", url, data=data, files={"video": (p.name, fh, "video/mp4")},
                    idempotent=False, upload=True,
                )
            body_text = resp.text or ""
            try:
                body = resp.json() if resp.content else {}
            except Exception:
                body = {}
            if resp.status_code >= 400 or (isinstance(body, dict) and not body.get("ok", True)):
                desc = str(
                    (body or {}).get("description") if isinstance(body, dict) else body_text
                )
                raise _map_telegram_error(resp.status_code or 400, desc, "sendVideo")
            result = body.get("result") if isinstance(body, dict) else None
            return result if isinstance(result, dict) else (body if isinstance(body, dict) else {})
        except ModuleError:
            raise
        except Exception as e:
            raise ModuleError(
                ModuleErrorCode.TRANSIENT,
                f"upload video: {mask_secrets(str(e))[:200]}",
                action="повторить",
                retryable=True,
            ) from e

    def send_photo(
        self,
        path: str | Path,
        *,
        caption: str = "",
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        p = Path(path)
        if not p.is_file():
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                f"фото не найдено: {p}",
                action="проверьте путь.",
            )
        size_mb = p.stat().st_size / (1024 * 1024)
        if size_mb > MAX_PHOTO_MB:
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                f"фото {size_mb:.1f} МБ > лимита {MAX_PHOTO_MB} МБ.",
                action="сожмите изображение.",
            )
        if self.dry_run:
            return self._call_json(
                "sendPhoto",
                {"chat_id": self.chat_id, "caption": (caption or "")[:MAX_CAPTION]},
            )
        url = self._url("sendPhoto")
        data: dict[str, Any] = {
            "chat_id": str(self.chat_id),
            "caption": (caption or "")[:MAX_CAPTION],
            "disable_notification": str(self.disable_notification).lower(),
        }
        if self.parse_mode:
            data["parse_mode"] = self.parse_mode
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        try:
            with open(p, "rb") as fh:
                resp = self._http.request(
                    "POST", url, data=data, files={"photo": (p.name, fh, "image/jpeg")},
                    idempotent=False, upload=True,
                )
            body_text = resp.text or ""
            try:
                body = resp.json() if resp.content else {}
            except Exception:
                body = {}
            if resp.status_code >= 400 or (isinstance(body, dict) and not body.get("ok", True)):
                desc = str(
                    (body or {}).get("description") if isinstance(body, dict) else body_text
                )
                raise _map_telegram_error(resp.status_code or 400, desc, "sendPhoto")
            result = body.get("result") if isinstance(body, dict) else None
            return result if isinstance(result, dict) else (body if isinstance(body, dict) else {})
        except ModuleError:
            raise
        except Exception as e:
            raise ModuleError(
                ModuleErrorCode.TRANSIENT,
                f"upload photo: {mask_secrets(str(e))[:200]}",
                action="повторить",
                retryable=True,
            ) from e

    def edit_message_text(
        self,
        message_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        link_preview_url: str | None = None,
    ) -> dict[str, Any]:
        text = (text or "")[:MAX_TEXT]
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "message_id": int(message_id),
            "text": text,
        }
        if self.parse_mode:
            payload["parse_mode"] = self.parse_mode
        preview: dict[str, Any] = {"is_disabled": False}
        if self.show_above:
            preview["show_above_text"] = True
        if link_preview_url:
            preview["url"] = link_preview_url
        payload["link_preview_options"] = preview
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._call_json("editMessageText", payload)

    def edit_message_media(self, message_id: int, *, media_type: str, media: str, caption: str = "") -> dict[str, Any]:
        payload={"chat_id": self.chat_id, "message_id": int(message_id), "media": {"type": str(media_type), "media": str(media)}}
        if caption:
            payload["media"]["caption"] = str(caption)[:1024]
            if self.parse_mode: payload["media"]["parse_mode"] = self.parse_mode
        return self._call_json("editMessageMedia", payload)

    def delete_message(self, message_id: int) -> bool:
        try:
            self._call_json(
                "deleteMessage",
                {"chat_id": self.chat_id, "message_id": int(message_id)},
            )
            return True
        except ModuleError as e:
            if e.code in (
                ModuleErrorCode.PLATFORM_REJECTED,
                ModuleErrorCode.FATAL,
                ModuleErrorCode.MEDIA_INVALID,
            ):
                logger.warning("telegram deleteMessage %s: %s", message_id, e.message)
                return False
            raise
