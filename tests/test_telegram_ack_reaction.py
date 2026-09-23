"""Галочка «сообщение дошло»: реакция бота на сообщение владельца.

У ботов в Telegram нет статуса «прочитано» — зелёная галочка означает только доставку.
Поэтому бот ставит реакцию 👀 на сообщение владельца (признак, что он его получил),
а когда я отвечаю — 👍 (признак, что прочитал и ответил).
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.telegram_transport import TelegramTransport


class _Rec:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def post(self, url, json=None, timeout=None, **kw):
        self.calls.append({"url": url, "json": json or {}})

        class _R:
            status_code = 200
            text = '{"ok":true}'

            @staticmethod
            def json():
                return {"ok": True}

        return _R()


def test_reaction_payload(monkeypatch):
    rec = _Rec()
    monkeypatch.setattr(httpx, "post", rec.post)
    tr = TelegramTransport("tok", on_message=None)
    assert tr.set_reaction(7004751908, 42, "👀") is True
    call = rec.calls[-1]
    assert call["url"].endswith("/setMessageReaction")
    assert call["json"]["chat_id"] == 7004751908
    assert call["json"]["message_id"] == 42
    assert call["json"]["reaction"] == [{"type": "emoji", "emoji": "👀"}]


def test_worker_reacts_only_when_enabled(monkeypatch):
    seen: list[tuple] = []
    rec = _Rec()
    monkeypatch.setattr(httpx, "post", rec.post)
    monkeypatch.setenv("TELEGRAM_ACK_REACTION", "👀")
    tr = TelegramTransport("tok", on_message=lambda chat, text: seen.append((chat, text)) or None)
    monkeypatch.setattr(tr, "set_reaction", lambda chat, mid, emoji: rec.calls.append(
        {"url": "react", "json": {"chat": chat, "mid": mid, "emoji": emoji}}) or True)
    tr._q.put((123, "привет", 79))
    th = threading.Thread(target=tr._worker, daemon=True)
    th.start()
    for _ in range(60):
        if seen:
            break
        time.sleep(0.05)
    tr._stop = True
    tr._q.put(None)
    th.join(timeout=3)
    reacts = [c for c in rec.calls if c["url"] == "react"]
    assert reacts and reacts[0]["json"]["emoji"] == "👀", "явно включённая реакция должна ставиться"


def test_reaction_needs_message_id(monkeypatch):
    rec = _Rec()
    monkeypatch.setattr(httpx, "post", rec.post)
    tr = TelegramTransport("tok", on_message=None)
    assert tr.set_reaction(1, None, "👀") is False
    assert rec.calls == []


def test_worker_reacts_to_incoming(monkeypatch):
    seen: list[tuple] = []
    rec = _Rec()
    monkeypatch.setattr(httpx, "post", rec.post)
    tr = TelegramTransport("tok", on_message=lambda chat, text: seen.append((chat, text)) or None)
    monkeypatch.setattr(tr, "set_reaction", lambda chat, mid, emoji: rec.calls.append(
        {"url": "react", "json": {"chat": chat, "mid": mid, "emoji": emoji}}) or True)

    tr._q.put((123, "привет", 78))
    th = threading.Thread(target=tr._worker, daemon=True)
    th.start()
    for _ in range(60):
        if seen:
            break
        time.sleep(0.05)
    tr._stop = True
    tr._q.put(None)
    th.join(timeout=3)

    assert seen, "on_message не вызван"
    reacts = [c for c in rec.calls if c["url"] == "react"]
    # по умолчанию реакции на входящие нет: 👀 владелец принимал за «прочитано»
    assert reacts == [], "авто-реакция не должна ставиться без TELEGRAM_ACK_REACTION"
