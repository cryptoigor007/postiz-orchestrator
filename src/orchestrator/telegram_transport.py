from __future__ import annotations

import logging
import os
import queue
import threading
import time
from collections.abc import Callable

import httpx

logger = logging.getLogger(__name__)


class TelegramTransport:
    """Long-poll + optional webhook-style local push. Heavy handlers run on worker queue."""

    def __init__(self, token: str | None = None, on_message: Callable[[int, str], str | None] | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.on_message = on_message
        self._offset = 0
        self._stop = False
        self._poll_thread: threading.Thread | None = None
        self._worker_thread: threading.Thread | None = None
        self._q: queue.Queue = queue.Queue()
        self._base = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.mode = os.getenv("TELEGRAM_MODE", "poll")  # poll | off
        # no_ack: не подтверждаем апдейты (offset=0), чтобы не «съедать» их у Postiz (/connect)
        self.no_ack = os.getenv("TELEGRAM_POLL_NO_ACK", "1") not in ("0", "false", "no")
        self._seen: set[int] = set()

    @property
    def enabled(self) -> bool:
        return bool(self.token) and self.mode != "off"

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        if not self.token:
            logger.info("[TG-mock -> %s] %s", chat_id, text[:200])
            return
        payload: dict = {"chat_id": chat_id, "text": text[:4000]}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            httpx.post(f"{self._base}/sendMessage", json=payload, timeout=30)
        except Exception:
            logger.exception("sendMessage failed")

    def start(self) -> None:
        if not self.enabled or self._poll_thread:
            return
        self._stop = False
        self._worker_thread = threading.Thread(target=self._worker, name="tg-worker", daemon=True)
        self._worker_thread.start()
        self._poll_thread = threading.Thread(target=self._loop, name="tg-poll", daemon=True)
        self._poll_thread.start()
        logger.info("Telegram transport started (mode=%s)", self.mode)

    def stop(self) -> None:
        self._stop = True
        self._q.put(None)
        for th in (self._poll_thread, self._worker_thread):
            if th:
                th.join(timeout=5)
        self._poll_thread = None
        self._worker_thread = None

    def push_update(self, chat_id: int, text: str) -> None:
        """For tests / webhook adapter."""
        self._q.put((chat_id, text))

    def _accept(self, upd: dict) -> bool:
        """Фильтр дублей в режиме no_ack; иначе двигаем offset."""
        uid = upd.get("update_id")
        if self.no_ack:
            if uid in self._seen:
                return False
            if uid is not None:
                self._seen.add(uid)
                if len(self._seen) > 5000:
                    self._seen = set(sorted(self._seen)[-2000:])
            return True
        if uid is not None:
            self._offset = uid + 1
        return True

    def _worker(self) -> None:
        while not self._stop:
            item = self._q.get()
            if item is None:
                break
            chat_id, text = item
            try:
                if self.on_message:
                    reply = self.on_message(chat_id, text)
                    if reply:
                        self.send_message(chat_id, reply)
            except Exception:
                logger.exception("handler failed")

    def _loop(self) -> None:
        while not self._stop:
            try:
                r = httpx.get(
                    f"{self._base}/getUpdates",
                    params={"offset": 0 if self.no_ack else self._offset, "timeout": 25},
                    timeout=30,
                )
                if r.status_code != 200:
                    time.sleep(3)
                    continue
                for upd in r.json().get("result", []):
                    if not self._accept(upd):
                        continue
                    msg = upd.get("message") or upd.get("edited_message")
                    if not msg:
                        cb = upd.get("callback_query")
                        if cb:
                            chat_id = ((cb.get("message") or {}).get("chat") or {}).get("id")
                            data = cb.get("data") or ""
                            if chat_id and data:
                                self._q.put((chat_id, f"/{data}"))
                            try:
                                httpx.post(f"{self._base}/answerCallbackQuery",
                                           json={"callback_query_id": cb.get("id")}, timeout=10)
                            except Exception:
                                pass
                        continue
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text") or ""
                    self._q.put((chat_id, text))
            except Exception:
                logger.exception("poll error")
                time.sleep(5)
