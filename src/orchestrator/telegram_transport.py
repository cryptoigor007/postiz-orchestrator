from __future__ import annotations

import logging
import os
import queue
import threading
import time
from collections.abc import Callable

import httpx

logger = logging.getLogger(__name__)

HTML_PREFIX = "\x00html\x00"


def split_text(text: str, limit: int = 3800) -> list[str]:
    """Разбивает длинный текст по строкам на части (лимит Telegram 4096)."""
    text = text or ""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    cur = ""
    for line in text.splitlines():
        while len(line) > limit:
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(line[:limit])
            line = line[limit:]
        if len(cur) + len(line) + 1 > limit:
            parts.append(cur)
            cur = line
        else:
            cur = (cur + "\n" + line) if cur else line
    if cur:
        parts.append(cur)
    return parts


class TelegramTransport:
    """Long-poll + optional webhook-style local push. Heavy handlers run on worker queue."""

    def __init__(self, token: str | None = None,
                 on_message: Callable[[int, str], str | None] | None = None,
                 load_seen: Callable[[], int] | None = None,
                 save_seen: Callable[[int], None] | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.on_message = on_message
        self._load_seen = load_seen
        self._save_seen = save_seen
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
        self._last_update_id = 0
        if self._load_seen:
            try:
                self._last_update_id = int(self._load_seen() or 0)
            except Exception:
                logger.warning("cannot load telegram seen watermark", exc_info=True)

    @property
    def enabled(self) -> bool:
        return bool(self.token) and self.mode != "off"

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        if not self.token:
            logger.info("[TG-mock -> %s] %s", chat_id, (text or "")[:200])
            return
        parse_mode = None
        if text and text.startswith(HTML_PREFIX):
            parse_mode = "HTML"
            text = text[len(HTML_PREFIX):]
        chunks = split_text(text or "")
        for i, chunk in enumerate(chunks):
            payload: dict = {"chat_id": chat_id, "text": chunk}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if reply_markup and i == len(chunks) - 1:
                payload["reply_markup"] = reply_markup
            try:
                r = httpx.post(f"{self._base}/sendMessage", json=payload, timeout=30)
                ok = False
                try:
                    ok = bool(r.json().get("ok"))
                except Exception:
                    ok = False
                if r.status_code == 429 and i == len(chunks) - 1:
                    # P1.10: короткая пауза по Retry-After (clamp 1..60) и один повтор
                    try:
                        wait = float(r.json().get("parameters", {}).get("retry_after") or 3)
                    except Exception:
                        wait = 3
                    import time as _t
                    _t.sleep(max(1.0, min(60.0, wait)))
                    r2 = httpx.post(f"{self._base}/sendMessage", json=payload, timeout=30)
                    try:
                        ok = bool(r2.json().get("ok"))
                    except Exception:
                        ok = False
                if not ok:
                    logger.warning("sendMessage not ok: status=%s body=%s",
                                   r.status_code, r.text[:200])
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

    def _next_offset(self) -> int:
        """В no_ack держим последние ~50 апдейтов неподтверждёнными (видны Postiz)."""
        if not self.no_ack:
            return self._offset
        return max(0, self._last_update_id - 50)

    def _accept(self, upd: dict) -> bool:
        """Фильтр дублей в режиме no_ack (с постоянной отметкой); иначе двигаем offset."""
        uid = upd.get("update_id")
        if uid is None:
            return True
        if self.no_ack:
            if uid <= self._last_update_id or uid in self._seen:
                return False
            self._seen.add(uid)
            if len(self._seen) > 5000:
                self._seen = set(sorted(self._seen)[-2000:])
            self._last_update_id = uid
            if self._save_seen:
                try:
                    self._save_seen(uid)
                except Exception:
                    logger.warning("cannot save telegram seen watermark", exc_info=True)
            return True
        self._last_update_id = max(self._last_update_id, uid)
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
                    params={"offset": self._next_offset(), "timeout": 25},
                    timeout=30,
                )
                if r.status_code != 200:
                    time.sleep(3)
                    continue
                new_count = 0
                for upd in r.json().get("result", []):
                    if not self._accept(upd):
                        continue
                    new_count += 1
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
                if new_count == 0 and self.no_ack:
                    # старые (неподтверждённые) апдейты возвращаются мгновенно — не долбим API
                    time.sleep(float(os.getenv("TELEGRAM_POLL_IDLE_SEC", "2")))
            except httpx.TransportError as e:
                logger.warning("poll transient error: %s", e)
                time.sleep(5)
            except Exception:
                logger.exception("poll error")
                time.sleep(5)
