#!/usr/bin/env python3
"""Minimal MCP (Model Context Protocol) server for the Orchestrator webapp API.

Stdio transport, JSON-RPC 2.0, newline-delimited. No third-party deps.

Env:
  ORCH_URL  base URL of the orchestrator webapp (default http://127.0.0.1:8080)
  ORCH_KEY  WEBAPP_ACCESS_KEY value (sent as X-Webapp-Key)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.getenv("ORCH_URL", "http://127.0.0.1:8080").rstrip("/")
KEY = os.getenv("ORCH_KEY", "")
PROTO = "2024-11-05"

TOOLS = [
    ("orch_status", "Текущий статус: счётчики и платформы", {}, "GET", "/webapp/api/status"),
    ("orch_metrics", "Метрики: аптайм, циклы, ошибки", {}, "GET", "/webapp/api/metrics"),
    ("orch_calendar", "Календарь запланированных публикаций", {}, "GET", "/webapp/api/calendar"),
    ("orch_queue", "Очередь публикаций", {}, "GET", "/webapp/api/queue"),
    ("orch_platforms", "Платформы и их лимиты/пауза", {}, "GET", "/webapp/api/platforms"),
    ("orch_failed", "Ошибки публикаций", {}, "GET", "/webapp/api/failed"),
    ("orch_tail", "Режим хвоста серий", {}, "GET", "/webapp/api/tail"),
    ("orch_roots", "Папки для сканирования + доступные корни", {}, "GET", "/webapp/api/roots"),
    ("orch_set_roots", "Задать папки для сканирования",
     {"roots": {"type": "array", "items": {"type": "string"}, "description": "Абсолютные пути"}},
     "POST", "/webapp/api/roots"),
    ("orch_browse", "Показать содержимое папки",
     {"path": {"type": "string"}, "root": {"type": "string"}}, "GET", "/webapp/api/browse"),
    ("orch_scan", "Запустить сканирование папок", {}, "POST", "/webapp/api/scan"),
    ("orch_pause", "Поставить все платформы на паузу", {}, "POST", "/webapp/api/pause"),
    ("orch_resume", "Возобновить все платформы", {}, "POST", "/webapp/api/resume"),
    ("orch_resume_platform", "Возобновить платформу",
     {"platform": {"type": "string"}}, "POST", "/webapp/api/resume_platform"),
    ("orch_series_end", "Включить/выключить режим хвоста (серия)",
     {"platform": {"type": "string"}, "enable": {"type": "boolean"}}, "POST", "/webapp/api/series_end"),
    ("orch_distribute", "Распределить длинные видео по слотам", {}, "POST", "/webapp/api/distribute"),
    ("orch_force_link", "Вручную обновить ссылку на пост",
     {"entity_id": {"type": "integer"}, "platform": {"type": "string"}, "url": {"type": "string"}},
     "POST", "/webapp/api/force_link"),
    ("orch_sync", "Синхронизировать статусы из Postiz", {}, "POST", "/webapp/api/sync"),
    ("orch_reconcile", "Реконсиляция с Postiz", {}, "POST", "/webapp/api/reconcile"),
    ("orch_backup", "Создать бэкап БД", {}, "POST", "/webapp/api/backup"),
    ("orch_schedule", "Разложить видео по слотам", {}, "POST", "/webapp/api/schedule"),
    ("orch_pause_platform", "Поставить платформу на паузу",
     {"platform": {"type": "string"}}, "POST", "/webapp/api/pause_platform"),
    ("orch_manual_plan", "Отчёт по ручным загрузкам", {}, "GET", "/webapp/api/manual/plan"),
    ("orch_manual_list", "Список ручных загрузок",
     {"status": {"type": "string"}, "platform": {"type": "string"}},
     "GET", "/webapp/api/manual/uploads"),
    ("orch_manual_scan", "Найти ручные загрузки",
     {"platform": {"type": "string"}}, "POST", "/webapp/api/manual/scan"),
    ("orch_manual_confirm", "Подтвердить сопоставление ручной загрузки",
     {"id": {"type": "integer"}, "entity_type": {"type": "string"},
      "entity_id": {"type": "integer"}, "apply_edits": {"type": "boolean"}},
     "POST", "/webapp/api/manual/uploads/{id}/confirm"),
    ("orch_manual_reject", "Отклонить ручную загрузку",
     {"id": {"type": "integer"}}, "POST", "/webapp/api/manual/uploads/{id}/reject"),
]


def _schema(props: dict) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": [],
        "additionalProperties": False,
    }


def _call(method: str, path: str, args: dict) -> tuple[bool, object]:
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if KEY:
        headers["X-Webapp-Key"] = KEY
    if method == "GET":
        q = {k: v for k, v in (args or {}).items() if v is not None}
        if q:
            url += "?" + urllib.parse.urlencode(q)
    else:
        data = json.dumps(args or {}).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            try:
                return True, json.loads(body)
            except Exception:
                return True, body
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode()[:500]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _tools_list() -> list[dict]:
    out = []
    for name, desc, props, method, path in TOOLS:
        out.append({
            "name": name,
            "description": f"{desc} [{method} {path}]",
            "inputSchema": _schema(props),
        })
    return out


def _tools_call(name: str, args: dict) -> dict:
    tool = next((t for t in TOOLS if t[0] == name), None)
    if not tool:
        return {"isError": True, "content": [{"type": "text", "text": f"unknown tool: {name}"}]}
    _, _, _, method, path = tool
    args = dict(args or {})
    if "{id}" in path:
        if "id" not in args:
            return {"isError": True, "content": [{"type": "text", "text": "id is required"}]}
        path = path.replace("{id}", str(args.pop("id")))
    ok, result = _call(method, path, args)
    text = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
    return {"isError": not ok, "content": [{"type": "text", "text": text}]}


def _respond(msg_id, result=None, error=None) -> None:
    payload = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        method = msg.get("method")
        mid = msg.get("id")
        params = msg.get("params") or {}
        if method == "initialize":
            _respond(mid, {
                "protocolVersion": PROTO,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "orchestrator", "version": "1.0.0"},
            })
        elif method in ("notifications/initialized", "initialized"):
            continue
        elif method == "tools/list":
            _respond(mid, {"tools": _tools_list()})
        elif method == "tools/call":
            _respond(mid, _tools_call(params.get("name", ""), params.get("arguments") or {}))
        elif method == "ping":
            _respond(mid, {})
        elif mid is not None:
            _respond(mid, error={"code": -32601, "message": f"method not found: {method}"})
    return 0



def _require_mcp_token() -> None:
    """S17: refuse to start MCP without ORCH_MCP_TOKEN in production-like envs."""
    import os
    tok = os.getenv("ORCH_MCP_TOKEN", "").strip()
    strict = os.getenv("ORCH_MCP_REQUIRE_TOKEN", "").strip() in ("1", "true", "yes")
    if strict and not tok:
        raise SystemExit("ORCH_MCP_TOKEN required (set ORCH_MCP_REQUIRE_TOKEN=0 to override)")

if __name__ == "__main__":
    _require_mcp_token()
    sys.exit(main())
