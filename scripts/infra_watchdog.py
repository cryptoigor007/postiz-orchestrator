#!/usr/bin/env python3
"""Инфра-вотчдог: проверяет панель, брокер, туннель и шлёт алерт в Telegram.

Запускается systemd-таймером. Алерты — с кулдауном (файл состояния).
"""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

STATE = Path("/var/lib/orchestrator-infra-watchdog.json")
COOLDOWN_SEC = int(os.getenv("INFRA_ALERT_COOLDOWN", "1800"))


def _env(path: str = "/opt/orchestrator/.env") -> dict:
    out = {}
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    except Exception:
        pass
    return out


def _chat_id() -> str:
    try:
        import yaml
        cfg = yaml.safe_load(Path("/opt/orchestrator/config.yaml").read_text())
        ids = (cfg.get("telegram") or {}).get("allowed_chat_ids") or []
        if ids:
            return str(ids[0])
    except Exception:
        pass
    return os.getenv("ORCH_ALERT_CHAT", "")


def _get(url: str, headers: dict | None = None, timeout: int = 10) -> int:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def _service_active(name: str) -> bool:
    try:
        r = subprocess.run(["systemctl", "is-active", "--quiet", name], timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def _should_alert(state: dict, key: str, now: float) -> bool:
    last = state.get(key, 0)
    return (now - last) >= COOLDOWN_SEC


def _notify(token: str, chat: str, text: str) -> None:
    if not token or not chat:
        return
    data = json.dumps({"chat_id": chat, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass


def main() -> int:
    env = _env()
    problems: list[str] = []

    if _get("http://127.0.0.1:8080/health") != 200:
        problems.append("webapp/оркестратор: /health не отвечает")
    broker = env.get("TOKEN_BROKER_URL", "")
    if broker:
        code = _get(broker.rstrip("/") + "/health",
                    {"X-Broker-Secret": env.get("TOKEN_BROKER_SECRET", "")})
        if code != 200:
            problems.append(f"токен-брокер: /health -> {code}")
    if not _service_active("cloudflared-webapp.service"):
        problems.append("туннель cloudflared: сервис не active")
    if not Path("/var/lib/cloudflared-webapp.url").is_file():
        problems.append("неизвестен публичный URL панели")

    now = time.time()
    state = {}
    try:
        state = json.loads(STATE.read_text())
    except Exception:
        state = {}
    for p in problems:
        key = p.split(":")[0]
        if _should_alert(state, key, now):
            _notify(env.get("TELEGRAM_BOT_TOKEN", ""), _chat_id(),
                    f"⚠️ ИНФРА-СБОЙ: {p}")
            state[key] = now
    STATE.write_text(json.dumps(state))
    if not problems:
        print("infra ok")
        return 0
    print("infra problems: " + "; ".join(problems))
    return 1


if __name__ == "__main__":
    sys.exit(main())
