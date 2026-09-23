#!/usr/bin/env python3
"""Ответ владельцу в Telegram + отметка прочитанных сообщений реакцией.

Зачем: у ботов в Telegram нет статуса «прочитано». Зелёная галочка у владельца означает
только доставку. Поэтому:
  • бот сам ставит 👀 на каждое входящее сообщение (признак «получил»);
  • этот скрипт, когда я отвечаю, ставит 👍 на сообщения, на которые отвечаю (признак «прочитал»).

Запуск на сервере из /opt/orchestrator:
    ./venv/bin/python tools/tg_say.py --react 204 205 --text-file /tmp/reply.html
    ./venv/bin/python tools/tg_say.py --react 204 "короткий текст"
    ./venv/bin/python tools/tg_say.py "текст без отметок"

Показать результат картинкой (скриншот «до/после») владельцу в чат:
    ./venv/bin/python tools/tg_say.py --photo /tmp/shots/after.png --caption "как стало"

Показ «я в процессе» (владелец просил видеть, что работа идёт):
    ./venv/bin/python tools/tg_say.py --typing              # разовый индикатор «печатает…»
    ./venv/bin/python tools/tg_say.py --typing-for 600      # держать индикатор 10 минут
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
import time

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from orchestrator.telegram_publish import TelegramPublisher
from orchestrator.telegram_transport import TelegramTransport

OWNER_CHAT_ID = 7004751908


def read_token() -> str:
    env_file = pathlib.Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        found = dict(re.findall(r"^([A-Z_]+)=(.*)$", env_file.read_text(encoding="utf-8"), re.M))
        token = (found.get("TELEGRAM_BOT_TOKEN") or "").strip()
        if token:
            return token
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def last_owner_messages(token: str, chat_id: int, limit: int = 5) -> list[int]:
    """Последние сообщения владельца (id) — чтобы отметить их прочитанными.

    `offset=-N` возвращает последние апдейты и не подтверждает их (не мешает опросу бота).
    """
    try:
        r = httpx.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": -limit, "limit": limit, "timeout": 0}, timeout=15,
        )
        out: list[int] = []
        for upd in reversed((r.json() or {}).get("result", [])):
            msg = upd.get("message") or {}
            if ((msg.get("chat") or {}).get("id")) == chat_id and msg.get("message_id"):
                out.append(int(msg["message_id"]))
        return out
    except Exception as exc:  # noqa: BLE001 — диагностика в stdout
        print("не удалось получить последние сообщения:", exc, file=sys.stderr)
        return []


def main() -> int:
    ap = argparse.ArgumentParser(description="Ответ в Telegram с отметкой прочитанного")
    ap.add_argument("text", nargs="?", default="", help="текст сообщения")
    ap.add_argument("--text-file", default="", help="файл с текстом (HTML допускается)")
    ap.add_argument("--react", nargs="*", type=int, default=[],
                    help="id сообщений владельца, на которые отвечаю (получат 👍); "
                         "указывать именно те id, на которые есть ответ")
    ap.add_argument("--chat", type=int, default=OWNER_CHAT_ID, help="куда отвечать")
    ap.add_argument("--photo", default="", metavar="ФАЙЛ",
                    help="отправить картинку (сообщение владельцу уходит подписью)")
    ap.add_argument("--caption", default="", help="подпись к картинке (если текст не задан позиционно)")
    ap.add_argument("--typing", action="store_true",
                    help="показать «печатает…» (один раз, ~5 секунд)")
    ap.add_argument("--typing-for", type=int, default=0, metavar="СЕК",
                    help="держать «печатает…» столько секунд (для долгой работы)")
    ap.add_argument("--emoji", default="👍", help="эмодзи отметки прочитанного")
    ap.add_argument("--react-last", type=int, default=0,
                    help="отметить столько последних сообщений владельца (по журналу Telegram)")
    args = ap.parse_args()

    text = pathlib.Path(args.text_file).read_text(encoding="utf-8") if args.text_file else args.text

    if not text.strip() and not (args.typing or args.typing_for or args.photo):
        print("пустой текст — нечего отправлять", file=sys.stderr)
        return 2

    token = read_token()
    if not token:
        print("нет TELEGRAM_BOT_TOKEN", file=sys.stderr)
        return 3

    if args.photo:
        pub_photo = TelegramPublisher(token, str(args.chat))
        sent_photo = pub_photo.send_photo(args.photo, text or args.caption)
        print("картинка отправлена:", sent_photo)
        react_ids = list(args.react)
        if react_ids:
            tr = TelegramTransport(token, on_message=None)
            for mid in react_ids:
                ok = tr.set_reaction(args.chat, mid, args.emoji)
                print(f"отметка {args.emoji} на сообщение {mid}: {'ок' if ok else 'не вышло'}")
        return 0

    if args.typing_for or args.typing:
        pub_typing = TelegramPublisher(token, str(args.chat))
        if args.typing_for:
            # Индикатор «печатает…» живёт ~5 секунд, поэтому повторяем каждые 4:
            # владелец всё это время видит, что работа идёт.
            stop_at = time.monotonic() + max(10, min(args.typing_for, 3600))
            shown = 0
            while time.monotonic() < stop_at:
                if pub_typing.send_chat_action():
                    shown += 1
                time.sleep(4)
            print(f"индикатор «печатает…» держался ~{shown * 4} сек")
        else:
            pub_typing.send_chat_action()
            print("индикатор «печатает…» показан")
        if not text.strip():
            return 0

    sent = TelegramPublisher(token, str(args.chat)).send_post(text)
    print("отправлено:", sent)

    react_ids = list(args.react)
    if args.react_last:
        react_ids += last_owner_messages(token, args.chat, args.react_last)
    if react_ids:
        tr = TelegramTransport(token, on_message=None)
        for mid in react_ids:
            ok = tr.set_reaction(args.chat, mid, args.emoji)
            print(f"отметка {args.emoji} на сообщение {mid}: {'ок' if ok else 'не вышло'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
