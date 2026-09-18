#!/usr/bin/env python3
"""Telegram <-> opencode bridge (stdio-free, stdlib only).

Long-polls a Telegram bot; for each message from the allowed chat it runs
`opencode run` (continuing a session) and sends the answer back.

Env:
  BRIDGE_BOT_TOKEN   Telegram bot token (dedicated bot)
  BRIDGE_CHAT_ID     allowed chat id (e.g. 7004751908)
  OPENCODE_BIN       path to opencode (default: opencode)
  OPENCODE_DIR       working directory (default: home)
  OPENCODE_MODEL     optional provider/model
  OPENCODE_SESSION   optional fixed session id (else uses --continue)
  OPENCODE_AUTO      "0" to disable auto-approve (default 1)
  BRIDGE_TIMEOUT     seconds per request (default 600)
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

TOKEN = os.getenv("BRIDGE_BOT_TOKEN", "")
CHAT_ID = str(os.getenv("BRIDGE_CHAT_ID", ""))
BIN = os.getenv("OPENCODE_BIN", "opencode")
WORKDIR = os.getenv("OPENCODE_DIR", os.path.expanduser("~"))
MODEL = os.getenv("OPENCODE_MODEL", "")
SESSION = os.getenv("OPENCODE_SESSION", "")
AUTO = os.getenv("OPENCODE_AUTO", "1") not in ("0", "false", "no")
TIMEOUT = int(os.getenv("BRIDGE_TIMEOUT", "600"))
API = f"https://api.telegram.org/bot{TOKEN}"
ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _post(method: str, payload: dict):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[tg] {method} failed: {e}", file=sys.stderr)
        return {}


def _get_updates(offset: int):
    url = f"{API}/getUpdates?" + urllib.parse.urlencode(
        {"offset": offset, "timeout": 25, "allowed_updates": json.dumps(["message"])}
    )
    try:
        with urllib.request.urlopen(url, timeout=35) as r:
            return json.loads(r.read().decode()).get("result", [])
    except Exception:
        return []


def _send(chat_id: str, text: str) -> None:
    text = ANSI.sub("", text).strip() or "(пусто)"
    for i in range(0, len(text), 3900):
        _post("sendMessage", {"chat_id": chat_id, "text": text[i:i + 3900]})


def _typing(chat_id: str) -> None:
    _post("sendChatAction", {"chat_id": chat_id, "action": "typing"})


def _run_opencode(prompt: str) -> str:
    args = [BIN, "run", "--dir", WORKDIR]
    if SESSION:
        args += ["--session", SESSION]
    else:
        args += ["--continue"]
    if AUTO:
        args.append("--auto")
    if MODEL:
        args += ["--model", MODEL]
    args.append(prompt)
    try:
        r = subprocess.run(args, cwd=WORKDIR, capture_output=True, text=True,
                           timeout=TIMEOUT)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if not out and err:
            out = err
        return out
    except subprocess.TimeoutExpired:
        return f"⏱ Таймаут {TIMEOUT}s"
    except Exception as e:
        return f"Ошибка запуска opencode: {e}"


def main() -> int:
    if not TOKEN or not CHAT_ID:
        print("BRIDGE_BOT_TOKEN and BRIDGE_CHAT_ID are required", file=sys.stderr)
        return 2
    print(f"[bridge] opencode={BIN} dir={WORKDIR} session={SESSION or '(continue)'}", file=sys.stderr)
    offset = 0
    while True:
        updates = _get_updates(offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message") or {}
            chat = str((msg.get("chat") or {}).get("id", ""))
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            if chat != CHAT_ID:
                _send(chat, "⛔ Нет доступа.")
                continue
            if text in ("/start", "/help"):
                _send(chat, "Пиши запрос — я выполню его через opencode (с MCP оркестратора и Postiz).")
                continue
            _typing(chat)
            answer = _run_opencode(text)
            _send(chat, answer)
        time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
