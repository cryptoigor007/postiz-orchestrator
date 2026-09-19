#!/usr/bin/env python3
"""Minimal MCP server for the Postiz public API (stdio, stdlib only).

Env:
  POSTIZ_URL  base URL (default https://192-168-100-60.sslip.io)
  POSTIZ_KEY  organization API key (Authorization header, raw)
  POSTIZ_VERIFY_TLS  "1" to verify TLS (default 0 — self-signed self-hosted)
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.getenv("POSTIZ_URL", "https://192-168-100-60.sslip.io").rstrip("/")
KEY = os.getenv("POSTIZ_KEY", "")
VERIFY = os.getenv("POSTIZ_VERIFY_TLS", "0").strip().lower() in ("1", "true", "yes", "on")
_CTX = ssl.create_default_context()
if not VERIFY:
    _CTX.check_hostname = False
    _CTX.verify_mode = ssl.CERT_NONE

PROTO = "2024-11-05"

TOOLS = [
    ("postiz_integrations", "Список подключённых каналов (id, provider)", {}, "GET", "/public/v1/integrations"),
    ("postiz_posts", "Список постов (заплан/недавние)", {}, "GET", "/public/v1/posts"),
    ("postiz_upload_from_url", "Загрузить медиа в Postiz по URL",
     {"url": {"type": "string"}}, "POST", "/public/v1/upload-from-url"),
    ("postiz_create", "Создать пост в Postiz",
     {"integration_id": {"type": "string"}, "content": {"type": "string"},
      "media_url": {"type": "string"}, "schedule_at": {"type": "string"},
      "as_draft": {"type": "boolean"}}, "POST", "__create__"),
    ("postiz_delete", "Удалить пост Postiz",
     {"id": {"type": "string"}}, "DELETE", "__delete__"),
    ("postiz_set_status", "Изменить статус поста",
     {"id": {"type": "string"}, "status": {"type": "string"}}, "POST", "__status__"),
]


def _schema(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": [], "additionalProperties": False}


def _req(method: str, path: str, body: dict | None = None):
    url = BASE + path
    headers = {"Accept": "application/json", "Authorization": KEY}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40, context=_CTX) as r:
            raw = r.read().decode()
            try:
                return True, json.loads(raw)
            except Exception:
                return True, raw
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode()[:500]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _create(args: dict):
    iid = args.get("integration_id")
    if not iid:
        return False, "integration_id is required"
    image = []
    if args.get("media_url"):
        ok, res = _req("POST", "/public/v1/upload-from-url", {"url": args["media_url"]})
        if not ok:
            return False, f"upload failed: {res}"
        image = [{"id": res.get("id"), "path": res.get("path")}]
    value = {"content": args.get("content", ""), "image": image}
    entry = {"integration": {"id": iid}, "value": [value], "settings": {}}
    body = {"type": "draft" if args.get("as_draft") else "schedule",
            "shortLink": False, "tags": [], "posts": [entry]}
    if args.get("schedule_at"):
        body["date"] = args["schedule_at"]
    else:
        body["type"] = "now"
        body["date"] = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return _req("POST", "/public/v1/posts", body)


def _tool_call(name: str, args: dict) -> dict:
    tool = next((t for t in TOOLS if t[0] == name), None)
    if not tool:
        return {"isError": True, "content": [{"type": "text", "text": f"unknown tool: {name}"}]}
    _, _, _, method, path = tool
    if path == "__create__":
        ok, res = _create(args)
    elif path == "__delete__":
        ok, res = _req("DELETE", f"/public/v1/posts/{args.get('id','')}")
    elif path == "__status__":
        ok, res = _req("PUT", f"/public/v1/posts/{args.get('id','')}/status", {"status": args.get("status", "")})
    elif method == "GET":
        p = path
        params = {}
        if name == "postiz_posts":
            import datetime
            now = datetime.datetime.utcnow()
            params = {"startDate": (now - datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "endDate": (now + datetime.timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if params:
            p += "?" + urllib.parse.urlencode(params)
        ok, res = _req("GET", p)
    else:
        ok, res = _req(method, path, args if args else {})
    text = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)
    return {"isError": not ok, "content": [{"type": "text", "text": text}]}


def _respond(mid, result=None, error=None):
    out = {"jsonrpc": "2.0", "id": mid}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
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
            _respond(mid, {"protocolVersion": PROTO,
                           "capabilities": {"tools": {"listChanged": False}},
                           "serverInfo": {"name": "postiz", "version": "1.0.0"}})
        elif method in ("notifications/initialized", "initialized"):
            continue
        elif method == "tools/list":
            _respond(mid, {"tools": [
                {"name": n, "description": d, "inputSchema": _schema(p)} for n, d, p, _, _ in TOOLS
            ]})
        elif method == "tools/call":
            _respond(mid, _tool_call(params.get("name", ""), params.get("arguments") or {}))
        elif method == "ping":
            _respond(mid, {})
        elif mid is not None:
            _respond(mid, error={"code": -32601, "message": f"method not found: {method}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
