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
from datetime import datetime, timedelta
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


def _health_ok(url: str, headers: dict | None = None, tries: int = 3,
               delay: float = 10.0) -> bool:
    """Несколько попыток, чтобы короткий рестарт сервиса не поднимал ложную тревогу."""
    for i in range(max(1, tries)):
        if _get(url, headers) == 200:
            return True
        if i + 1 < tries:
            time.sleep(delay)
    return False


def _db_query(sql: str, args: tuple = ()) -> list[dict]:
    """SELECT через sqlite3. Схема — src/orchestrator/db.py (без updated_at)."""
    db_path = os.getenv("ORCH_DB", "/opt/orchestrator/data/data.sqlite")
    try:
        import sqlite3
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception:
        return []


def _orch_alerts() -> list[str]:
    """Алерты P1 по реальной схеме БД (db.py).

    entity_platform_status: НЕТ updated_at.
    waiting_for_youtube — это last_error при status='ready', время — postiz_scheduled_for.
    publish_log: колонка details (мн.ч.); action — фактические строки publisher
    (upload_fail, create_fail, safety_block, orphan_* …), не ModuleErrorCode.
    Время сравниваем ISO-строками в локальном времени (как пишет ядро):
    datetime('now') в SQLite — UTC и ломал бы пороги в не-UTC поясах.
    Token/auth_status алерты — с P2 (token_store), не в P1.
    """
    out: list[str] = []
    stuck_min = int(os.getenv("ORCH_WAITING_YT_MIN", "30"))

    # 1) «застрявшие» waiting_for_youtube
    cutoff_stuck = (datetime.now() - timedelta(minutes=stuck_min)).isoformat()
    rows = _db_query(
        """
        SELECT entity_id, entity_type, platform, postiz_scheduled_for, last_error
        FROM entity_platform_status
        WHERE status = 'ready'
          AND last_error = 'waiting_for_youtube'
          AND postiz_scheduled_for IS NOT NULL
          AND postiz_scheduled_for <= ?
        LIMIT 10
        """,
        (cutoff_stuck,),
    )
    if rows:
        ids = ", ".join(
            f"{r.get('entity_type')}/{r.get('entity_id')}@{r.get('platform')}"
            for r in rows
        )
        out.append(f"waiting_for_youtube: >{stuck_min} мин ({ids})")

    # 2) всплеск upload_fail / create_fail за 24 ч (фактические action из publisher)
    cutoff_day = (datetime.now() - timedelta(days=1)).isoformat()
    err_rows = _db_query(
        """
        SELECT action, COUNT(*) AS cnt
        FROM publish_log
        WHERE created_at >= ?
          AND action IN (
            'upload_fail', 'create_fail', 'safety_block',
            'orphan_cleanup', 'orphan_delete'
          )
        GROUP BY action
        """,
        (cutoff_day,),
    )
    if err_rows:
        parts = [f"{r['action']}×{r['cnt']}" for r in err_rows]
        total = sum(int(r["cnt"]) for r in err_rows)
        if total >= 3:  # антишум: один-два сбоя не алертим
            out.append(f"publish failures 24ч: {total} ({', '.join(parts)})")

    # 3) last_error с типичными auth/quota текстами (не ModuleErrorCode)
    auth_rows = _db_query(
        """
        SELECT entity_id, entity_type, platform, last_error
        FROM entity_platform_status
        WHERE last_error IS NOT NULL AND last_error != ''
          AND (
            lower(last_error) LIKE '%quota%'
            OR lower(last_error) LIKE '%invalid_grant%'
            OR lower(last_error) LIKE '%unauthorized%'
            OR lower(last_error) LIKE '%auth%'
            OR lower(last_error) LIKE '%token%'
          )
          AND status NOT IN ('published', 'deleted')
        LIMIT 5
        """
    )
    if auth_rows:
        sample = "; ".join(
            f"{r.get('entity_type')}/{r.get('entity_id')}: "
            f"{(r.get('last_error') or '')[:60]}"
            for r in auth_rows
        )
        out.append(f"auth/quota last_error: {sample}")

    return out


def main() -> int:
    env = _env()
    problems: list[str] = []

    if not _health_ok("http://127.0.0.1:8080/health"):
        problems.append("webapp/оркестратор: /health не отвечает")
    broker = env.get("TOKEN_BROKER_URL", "")
    if broker:
        if not _health_ok(broker.rstrip("/") + "/health",
                          {"X-Broker-Secret": env.get("TOKEN_BROKER_SECRET", "")},
                          tries=2, delay=5.0):
            problems.append("токен-брокер: /health не отвечает")
    if not _service_active("cloudflared-webapp.service"):
        problems.append("туннель cloudflared: сервис не active")
    if not Path("/var/lib/cloudflared-webapp.url").is_file():
        problems.append("неизвестен публичный URL панели")

    # защита от повторного включения сетевого «спама» (война маршрутов и шторм переподключений)
    for unit in ("pve-wifi-route-watchdog.service", "route-guard.service",
                 "usb-net-monitor.service", "broll-downloader.service"):
        if _service_active(unit):
            problems.append(f"опасный юнит активен: {unit} (сетевой шторм)")
    try:
        rg = subprocess.run(
            ["pgrep", "-f", r"/usr/local/sbin/(pve-wifi-route-watchdog|route-guard|network-failover)"],
            capture_output=True, text=True, timeout=10)
        if rg.returncode == 0:
            problems.append("опасный сетевой скрипт запущен вручную (война маршрутов)")
    except Exception:
        pass

    # --- дополнительные алерты оркестратора (Пакет 1.2) ---
    problems.extend(_orch_alerts())

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
