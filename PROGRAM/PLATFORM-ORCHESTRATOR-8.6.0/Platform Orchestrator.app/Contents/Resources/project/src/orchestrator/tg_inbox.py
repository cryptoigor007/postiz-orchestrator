"""Надёжный «входящий ящик» сообщений из Telegram.

Зачем: сообщение не должно теряться, если в этот момент журнал никто не смотрит.
Каждое входящее дописывается в `data/tg_inbox/inbox.jsonl` и остаётся там, пока его
не отметят прочитанным (`tools/tg_inbox.py --ack`). Поэтому пропущенные сообщения
видны всегда — даже если оркестратор или агент был недоступен часами.

Каталог задаётся `TG_INBOX_DIR`, по умолчанию `data/tg_inbox` (внутри каталога
данных, а значит попадает и в бэкап).
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024


def inbox_dir(directory: str | Path | None = None) -> Path:
    if directory is not None:
        return Path(directory)
    env = os.getenv("TG_INBOX_DIR", "").strip()
    return Path(env) if env else Path("data") / "tg_inbox"


def inbox_file(directory: str | Path | None = None) -> Path:
    return inbox_dir(directory) / "inbox.jsonl"


def seen_file(directory: str | Path | None = None) -> Path:
    """Файл со списком обработанных номеров сообщений (не «максимум»!).

    Раньше здесь лежало одно число — максимальный обработанный номер, и любое
    сообщение с меньшим номером считалось прочитанным. Из-за этого случайный
    большой номер (например, тестовый) «съедал» реальные сообщения владельца.
    """
    return inbox_dir(directory) / "seen_ids.json"


def append_message(
    chat_id: int | None,
    message_id: int | None,
    text: str,
    *,
    directory: str | Path | None = None,
    ts: float | None = None,
    kind: str = "message",
    extra: dict | None = None,
) -> Path | None:
    """Дописать входящее. Никогда не бросает: приём сообщений важнее учёта."""
    try:
        d = inbox_dir(directory)
        d.mkdir(parents=True, exist_ok=True)
        path = inbox_file(d)
        if path.exists() and path.stat().st_size > MAX_BYTES:
            path.replace(path.with_name(path.name + ".1"))
        rec = {
            "ts": ts if ts is not None else time.time(),
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "kind": kind,
        }
        if extra:
            rec.update(extra)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return path
    except Exception:
        logger.warning("cannot write telegram inbox", exc_info=True)
        return None


def annotate_text(message_id: int | None, text: str,
                  directory: str | Path | None = None) -> bool:
    """Дописать текст (расшифровку голосового) в уже сохранённую запись.

    Файл маленький, поэтому перезапись целиком: зато запись остаётся одна и её
    так же отмечают прочитанной по номеру сообщения.
    """
    mid = _as_int(message_id)
    if not mid or not text:
        return False
    path = inbox_file(directory)
    if not path.exists():
        return False
    recs = read_messages(directory)
    changed = False
    for rec in recs:
        if _as_int(rec.get("message_id")) != mid:
            continue
        if str(rec.get("voice_text") or "").strip() == text.strip():
            continue
        marker = str(rec.get("text", ""))
        # оставляем пометку «текст не расшифрован» только если расшифровки нет
        marker = marker.split(" Повтор")[0] if " Повтор" in marker else marker
        for old_text in (rec.get("voice_text"),):
            if old_text:
                marker = marker.replace(str(old_text), "").strip()
        rec["text"] = f"{marker} {text}".strip() if marker else text
        rec["voice_text"] = text
        rec["kind"] = "voice_text"
        changed = True
    if not changed:
        return False
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return True


def read_messages(directory: str | Path | None = None) -> list[dict]:
    """Все записи, от старых к новым. Битые строки пропускаются."""
    path = inbox_file(directory)
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def seen_ids(directory: str | Path | None = None) -> set[int]:
    """Номера сообщений, которые уже обработаны."""
    try:
        data = json.loads(seen_file(directory).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(data, list):
        return set()
    return {_as_int(x) for x in data if _as_int(x)}


def last_seen(directory: str | Path | None = None) -> int:
    """Наибольший обработанный номер (0 — ничего не обработано). Только для справки."""
    ids = seen_ids(directory)
    return max(ids) if ids else 0


def mark_seen(message_id: int | None, directory: str | Path | None = None) -> int:
    """Отметить сообщение обработанным. Прочитанным становится ровно оно, не «всё до него»."""
    mid = _as_int(message_id)
    ids = seen_ids(directory)
    if mid:
        ids.add(mid)
    d = inbox_dir(directory)
    d.mkdir(parents=True, exist_ok=True)
    seen_file(d).write_text(json.dumps(sorted(ids)[-5000:]), encoding="utf-8")
    return mid


def unread(directory: str | Path | None = None, *, after: int | None = None) -> list[dict]:
    """Непрочитанные, от старых к новым.

    `after` — не показывать записи с номером не больше указанного (для точечных проверок).
    Записи без номера сообщения не возвращаются: их нельзя отметить.
    """
    ids = seen_ids(directory)
    skip_upto = _as_int(after)
    out: list[dict] = []
    for rec in read_messages(directory):
        mid = _as_int(rec.get("message_id"))
        if not mid or mid in ids:
            continue
        if skip_upto and mid <= skip_upto:
            continue
        out.append(rec)
    return out


def wait_for_new(
    directory: str | Path | None = None,
    *,
    timeout: float = 0.0,
    poll: float = 2.0,
    after: int | None = None,
) -> dict | None:
    """Ждать сообщение новее отметки. `timeout=0` — ждать бесконечно."""
    deadline = None if timeout <= 0 else time.monotonic() + timeout
    while True:
        items = unread(directory, after=after)
        if items:
            return items[0]
        if deadline is not None and time.monotonic() >= deadline:
            return None
        time.sleep(poll)
