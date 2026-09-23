"""Публикация в Telegram напрямую через Bot API (режим `telegram.send_via=bot`).

Зачем отдельный путь, если есть Postiz: Postiz всегда ставит превью ссылки
**под** текстом поста. Bot API 7.0+ умеет `link_preview_options.show_above_text` —
карточка ролика встаёт **над** текстом, а под ней описание (как просили для канала).
Заодно доступны HTML-разметка, выбор ссылки для превью (`link_preview_options.url`,
иначе Telegram берёт первую ссылку из текста — например плейлист) и inline-кнопка.

Идентификатор такого поста в нашей БД: `tg:<message_id>`; маршрутизацию по нему
делает `postiz.PostizRouter`, поэтому весь остальной код (панель, синхронизация,
удаление) продолжает работать без изменений.
"""

from __future__ import annotations

import logging
import pathlib
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BOT_ID_PREFIX = "tg:"
API_BASE = "https://api.telegram.org"
# Bot API: text 1..4096 символов после разбора сущностей
MAX_TEXT = 4000


def is_bot_post_id(post_id: Any) -> bool:
    """Наш ли это пост (отправлен ботом), а не пост Postiz."""
    return str(post_id or "").startswith(BOT_ID_PREFIX)


def message_id_of(post_id: Any) -> int | None:
    s = str(post_id or "")
    if not s.startswith(BOT_ID_PREFIX):
        return None
    try:
        return int(s[len(BOT_ID_PREFIX):])
    except ValueError:
        return None


class TelegramPublisher:
    """Минимальный клиент Bot API: sendMessage / deleteMessage / editMessageText."""

    def __init__(
        self,
        token: str,
        chat_id: int | str,
        *,
        show_above: bool = True,
        prefer_large: bool = True,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.token = (token or "").strip()
        self.chat_id = chat_id
        self.show_above = bool(show_above)
        self.prefer_large = bool(prefer_large)
        self.timeout = timeout
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self.token) and bool(self.chat_id)

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Telegram Bot API не настроен: нет токена или chat_id")
        url = f"{API_BASE}/bot{self.token}/{method}"
        with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
            resp = client.post(url, json=payload)
        return self._parse(method, resp)

    @staticmethod
    def _parse(method: str, resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code >= 400:
            raise RuntimeError(f"telegram {method} {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except Exception as e:  # pragma: no cover - неожиданный ответ
            raise RuntimeError(f"telegram {method}: не JSON: {resp.text[:200]}") from e
        if not data.get("ok"):
            raise RuntimeError(f"telegram {method} not ok: {str(data.get('description'))[:300]}")
        return data.get("result") or {}

    def send_photo(self, path: str | pathlib.Path, caption: str = "") -> str:
        """Показать владельцу картинку (скриншот «до/после») — он хочет видеть, а не читать описание.

        Возвращает `tg:<message_id>`, как и `send_post`.
        """
        if not self.enabled:
            raise RuntimeError("Telegram Bot API не настроен: нет токена или chat_id")
        file = pathlib.Path(path)
        if not file.is_file():
            raise RuntimeError(f"нет файла для отправки: {file}")
        url = f"{API_BASE}/bot{self.token}/sendPhoto"
        data: dict[str, Any] = {"chat_id": str(self.chat_id)}
        text = (caption or "").strip()
        if text:
            data["caption"] = text[:1024]
            data["parse_mode"] = "HTML"
        suffix = file.suffix.lower().lstrip(".") or "png"
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(suffix, "image/png")
        with file.open("rb") as fh, httpx.Client(timeout=self.timeout, transport=self._transport) as client:
            resp = client.post(url, data=data, files={"photo": (file.name, fh, mime)})
        try:
            res = self._parse("sendPhoto", resp)
        except RuntimeError as e:
            if "parse entities" not in str(e):
                raise
            logger.warning("подпись к картинке не разобралась, шлю простым текстом: %s", e)
            data.pop("parse_mode", None)
            with file.open("rb") as fh, httpx.Client(timeout=self.timeout, transport=self._transport) as client:
                resp = client.post(url, data=data, files={"photo": (file.name, fh, mime)})
            res = self._parse("sendPhoto", resp)
        mid = res.get("message_id")
        if mid is None:
            raise RuntimeError("telegram sendPhoto: нет message_id в ответе")
        return f"{BOT_ID_PREFIX}{mid}"

    def send_post(self, text: str, *, buttons: list[dict[str, str]] | None = None,
                  preview_url: str | None = None) -> str:
        """Отправить пост. Возвращает id в нашем формате (`tg:<message_id>`)."""
        body = (text or "").strip()
        if len(body) > MAX_TEXT:
            body = body[:MAX_TEXT - 1].rstrip() + "…"
        preview: dict[str, Any] = {
            "show_above_text": self.show_above,
            "prefer_large_media": self.prefer_large,
        }
        if preview_url:
            preview["url"] = preview_url
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": body,
            "parse_mode": "HTML",
            "link_preview_options": preview,
        }
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [buttons]}
        try:
            res = self._call("sendMessage", payload)
        except RuntimeError as e:
            # Телеграм ругается на «неправильные» угловые скобки в тексте
            # (`can't parse entities`, например «<проект>» вместо тега). Сообщение терять нельзя:
            # повторяем без разметки — текст дойдёт целиком, просто без жирного.
            if "parse entities" not in str(e):
                raise
            logger.warning("telegram HTML не разобрался, отправляю простым текстом: %s", e)
            payload.pop("parse_mode", None)
            res = self._call("sendMessage", payload)
        mid = res.get("message_id")
        if mid is None:
            raise RuntimeError("telegram sendMessage: нет message_id в ответе")
        return f"{BOT_ID_PREFIX}{mid}"

    def send_chat_action(self, action: str = "typing") -> bool:
        """Показать владельцу, что бот работает: «печатает…» в шапке чата.

        У ботов нет «прочитано», зато есть sendChatAction — индикатор держится ~5 секунд,
        поэтому для долгой работы его повторяют (см. tools/tg_say.py --typing-for).
        """
        try:
            self._call("sendChatAction", {"chat_id": self.chat_id, "action": action})
            return True
        except Exception:
            logger.warning("telegram sendChatAction не сработал", exc_info=True)
            return False

    def delete_post(self, post_id: str) -> None:
        mid = message_id_of(post_id)
        if mid is None:
            return
        try:
            self._call("deleteMessage", {"chat_id": self.chat_id, "message_id": mid})
        except RuntimeError as e:
            # повторное удаление/старый пост — не повод падать
            logger.warning("telegram deleteMessage %s: %s", mid, e)

    def edit_text(self, post_id: str, text: str,
                  buttons: list[dict[str, str]] | None = None) -> None:
        mid = message_id_of(post_id)
        if mid is None:
            return
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "message_id": mid,
            "text": (text or "")[:MAX_TEXT],
            "parse_mode": "HTML",
            "link_preview_options": {
                "show_above_text": self.show_above,
                "prefer_large_media": self.prefer_large,
            },
        }
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [buttons]}
        self._call("editMessageText", payload)


def create_telegram_publisher(cfg: Any) -> TelegramPublisher | None:
    """Собрать издателя, если он включён в конфиге (иначе None — работает Postiz).

    Токен берём из окружения (`TELEGRAM_BOT_TOKEN`), как и остальной код бота.
    """
    import os

    tcfg = getattr(cfg, "platforms", {}).get("telegram")
    if not tcfg or not getattr(tcfg, "enabled", True):
        return None
    if str(getattr(tcfg, "send_via", "postiz") or "postiz").lower() != "bot":
        return None
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(tcfg, "publish_chat_id", "") or ""
    if not token or not chat_id:
        logger.warning(
            "telegram.send_via=bot, но нет TELEGRAM_BOT_TOKEN или "
            "platforms.telegram.publish_chat_id — остаёмся на Postiz"
        )
        return None
    return TelegramPublisher(token, chat_id,
                             show_above=bool(getattr(tcfg, "link_preview_above", True)))
