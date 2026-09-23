from __future__ import annotations

import logging
import os
import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from . import tg_inbox, voice_stt

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
        self._file_base = (f"https://api.telegram.org/file/bot{self.token}"
                           if self.token else "")
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

    def set_reaction(self, chat_id: int, message_id: int | None, emoji: str) -> bool:
        """Поставить реакцию на сообщение.

        У ботов в Telegram нет «прочитано» — галочка у владельца означает только доставку.
        Реакция на его сообщение и есть честный признак, что бот его получил/разобрал.
        """
        if not self.token or not message_id:
            return False
        try:
            r = httpx.post(
                f"{self._base}/setMessageReaction",
                json={"chat_id": chat_id, "message_id": int(message_id),
                      "reaction": [{"type": "emoji", "emoji": emoji}]},
                timeout=15,
            )
            try:
                ok = bool(r.json().get("ok"))
            except Exception:
                ok = False
            if not ok:
                logger.info("setMessageReaction not ok: %s %s", r.status_code, r.text[:160])
            return ok
        except Exception:
            logger.warning("setMessageReaction failed", exc_info=True)
            return False

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

    def _download_file(self, file_id: str | None, message_id: int | None, suffix: str,
                       subdir: str) -> str | None:
        """Скачать файл из Telegram (getFile). Лимит скачивания ботом — 20 МБ."""
        if not file_id or not message_id:
            return None
        try:
            resp = httpx.get(f"{self._base}/getFile", params={"file_id": file_id}, timeout=30)
            resp.raise_for_status()
            info = (resp.json() or {}).get("result") or {}
            remote = info.get("file_path") or ""
            if not remote:
                logger.warning("telegram getFile не вернул file_path для %s", message_id)
                return None
            size = int(info.get("file_size") or 0)
            if size > 20 * 1024 * 1024:
                logger.warning("file too big for bot download: %s bytes (msg %s)", size, message_id)
                return None
            out_dir = tg_inbox.inbox_dir().parent / subdir
            out_dir.mkdir(parents=True, exist_ok=True)
            out = (out_dir / f"{message_id}{Path(remote).suffix or suffix}").resolve()
            with httpx.stream("GET", f"{self._file_base}/{remote}", timeout=60) as r:
                r.raise_for_status()
                with out.open("wb") as fh:
                    for chunk in r.iter_bytes(65536):
                        fh.write(chunk)
            logger.info("media saved: %s", out)
            return str(out)
        except Exception:
            logger.warning("cannot download telegram media (msg %s)", message_id, exc_info=True)
            return None

    def _download_voice(self, msg: dict) -> str | None:
        """Скачать голосовое/кружок в data/tg_voice, чтобы его можно было расшифровать."""
        item = msg.get("voice") or msg.get("video_note") or msg.get("audio") or {}
        return self._download_file(item.get("file_id"), msg.get("message_id"), ".oga", "tg_voice")

    def _download_photo(self, msg: dict) -> str | None:
        """Скачать фото владельца (обычно скриншот панели) — берём самый крупный размер.

        Скриншоты нужны, чтобы смотреть на панель глазами владельца: папка data/tg_media,
        файл можно забрать по ssh и посмотреть.
        """
        sizes = msg.get("photo") or []
        if sizes:
            best = max(sizes, key=lambda s: (int(s.get("file_size") or 0),
                                             int(s.get("width") or 0) * int(s.get("height") or 0)))
            return self._download_file(best.get("file_id"), msg.get("message_id"), ".jpg", "tg_media")
        doc = msg.get("document") or {}
        mime = str(doc.get("mime_type") or "")
        if mime.startswith("image/"):
            return self._download_file(doc.get("file_id"), msg.get("message_id"), ".jpg", "tg_media")
        return None

    def recover_voices(self, directory: str | None = None) -> int:
        """Расшифровать голосовые, оставшиеся без текста (например, после перезапуска службы)."""
        if not voice_stt.enabled() or not voice_stt.available():
            return 0
        started = 0
        for rec in tg_inbox.read_messages(directory):
            path = rec.get("voice_file")
            text = str(rec.get("text") or "")
            if path and "не расшифрован" in text and not rec.get("voice_text"):
                self._transcribe_later(rec.get("message_id"), path)
                started += 1
        if started:
            logger.info("voice stt recovery started for %d message(s)", started)
        return started

    def _transcribe_later(self, message_id: int | None, path: str) -> None:
        """Расшифровать голосовое в фоне и дописать текст в ящик (резерв, когда Mac недоступен).

        В отдельном потоке, чтобы не задерживать приём остальных сообщений.
        """
        if not voice_stt.enabled() or not voice_stt.available():
            return

        def work() -> None:
            text = voice_stt.transcribe_file(path)
            if text:
                tg_inbox.annotate_text(message_id, text)

        threading.Thread(target=work, name=f"stt-{message_id}", daemon=True).start()

    @staticmethod
    def _message_text(msg: dict) -> str:
        """Текст сообщения. Голосовые/кружки/аудио текстом не приходят — помечаем их явно,
        иначе такое сообщение выглядит пустым и теряется."""
        text = msg.get("text") or msg.get("caption") or ""
        if text:
            return text
        for key, label in (("voice", "голосовое"), ("video_note", "видео-кружок"),
                           ("audio", "аудио"), ("video", "видео")):
            item = msg.get(key)
            if isinstance(item, dict):
                dur = item.get("duration")
                tail = f" {dur} сек" if dur else ""
                name = item.get("file_name") or ""
                extra = f" «{name}»" if name else ""
                return f"[{label}{tail}{extra} — текст не расшифрован]"
        for key, label in (("photo", "фото"), ("document", "файл"), ("sticker", "стикер")):
            if msg.get(key):
                return f"[{label} — без текста]"
        return ""

    def _enqueue(self, chat_id: int, text: str, message_id: int | None = None,
                 extra: dict | None = None) -> None:
        """Входящее: в очередь на обработку И в надёжный ящик (чтобы не потерялось)."""
        tg_inbox.append_message(chat_id, message_id, text, extra=extra)
        self._q.put((chat_id, text, message_id))

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
            chat_id, text = item[0], item[1]
            message_id = item[2] if len(item) > 2 else None
            # Реакцию на входящее по умолчанию НЕ ставим: владелец читал 👀 как «прочитал».
            # Честный сигнал — 👍 на том сообщении, на которое я реально отвечаю (tools/tg_say.py).
            # Если когда-нибудь понадобится авто-подтверждение, включается через TELEGRAM_ACK_REACTION.
            ack = os.getenv("TELEGRAM_ACK_REACTION", "").strip()
            if message_id and ack:
                self.set_reaction(chat_id, message_id, ack)
            # след в журнале: что и кто написал боту (ответы владельца видно в journalctl)
            logger.info("TG in %s (msg %s): %s", chat_id, message_id,
                        (text or "").replace("\n", " ")[:3900])
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
                                self._enqueue(chat_id, f"/{data}",
                                              (cb.get("message") or {}).get("message_id"))
                            try:
                                httpx.post(f"{self._base}/answerCallbackQuery",
                                           json={"callback_query_id": cb.get("id")}, timeout=10)
                            except Exception:
                                pass
                        continue
                    chat_id = msg["chat"]["id"]
                    extra = None
                    if msg.get("voice") or msg.get("video_note"):
                        saved = self._download_voice(msg)
                        if saved:
                            extra = {"voice_file": saved}
                            self._transcribe_later(msg.get("message_id"), saved)
                    elif msg.get("photo") or (msg.get("document") or {}).get("mime_type", "").startswith("image/"):
                        shot = self._download_photo(msg)
                        if shot:
                            extra = {"media_file": shot}
                    self._enqueue(chat_id, self._message_text(msg), msg.get("message_id"),
                                  extra=extra)
                if new_count == 0 and self.no_ack:
                    # старые (неподтверждённые) апдейты возвращаются мгновенно — не долбим API
                    time.sleep(float(os.getenv("TELEGRAM_POLL_IDLE_SEC", "2")))
            except httpx.TransportError as e:
                logger.warning("poll transient error: %s", e)
                time.sleep(5)
            except Exception:
                logger.exception("poll error")
                time.sleep(5)
