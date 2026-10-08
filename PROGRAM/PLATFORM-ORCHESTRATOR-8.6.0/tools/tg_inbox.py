#!/usr/bin/env python3
"""Входящие сообщения владельца из Telegram: ничего не теряется.

Зачем: сообщение могло прийти, пока журнал никто не смотрел. Все входящие лежат
в `data/tg_inbox/inbox.jsonl` (см. `orchestrator.tg_inbox`), поэтому их всегда
можно достать и отметить прочитанными.

Примеры:
  ./venv/bin/python tools/tg_inbox.py --unread          # что пропущено
  ./venv/bin/python tools/tg_inbox.py --ack 234 235     # отметить прочитанными
  ./venv/bin/python tools/tg_inbox.py --follow          # сторож: покажет пропущенное
                                                        # и будет ждать новое сообщение
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator import tg_inbox  # noqa: E402


def show(rec: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(rec, ensure_ascii=False))
        return
    print(f"msg {rec.get('message_id')} | chat {rec.get('chat_id')} | "
          f"{rec.get('kind', 'message')}\n{rec.get('text', '')}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Надёжный ящик входящих из Telegram")
    ap.add_argument("--unread", action="store_true", help="показать непрочитанные")
    ap.add_argument("--ack", nargs="*", type=int, metavar="MSG_ID",
                    help="отметить сообщения прочитанными")
    ap.add_argument("--follow", action="store_true",
                    help="показать пропущенное и ждать новое (одно сообщение и выход)")
    ap.add_argument("--timeout", type=float, default=0.0,
                    help="сколько секунд ждать в --follow (0 — бесконечно)")
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    ap.add_argument("--dir", default=None, help="каталог ящика (по умолчанию data/tg_inbox)")
    args = ap.parse_args()

    if args.ack is not None:
        for mid in args.ack:
            tg_inbox.mark_seen(mid, args.dir)
            print(f"прочитано: {mid}")
        return 0

    if args.follow:
        missed = tg_inbox.unread(args.dir)
        for rec in missed:
            show(rec, args.json)
        if missed:
            return 0
        rec = tg_inbox.wait_for_new(args.dir, timeout=args.timeout)
        if rec is None:
            print("тишина: новых сообщений нет", file=sys.stderr)
            return 1
        show(rec, args.json)
        return 0

    items = tg_inbox.unread(args.dir)
    if not items:
        print("непрочитанных нет")
        return 0
    for rec in items:
        show(rec, args.json)
    print(f"всего непрочитанных: {len(items)} (отметить: --ack <id> ...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
