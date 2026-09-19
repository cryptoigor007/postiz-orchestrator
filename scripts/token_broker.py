#!/usr/bin/env python3
"""Postiz OAuth token broker (runs on the Postiz VM).

Reads a platform channel token from the Postiz DB (via docker exec) and serves
it over HTTP to the orchestrator (which cannot reach the docker network).

Env:
  BROKER_SECRET      shared secret (required)
  BROKER_BIND        bind address (default 0.0.0.0)
  BROKER_PORT        port (default 9099)
  BROKER_PLATFORMS   comma list allowed (default youtube)
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

SECRET = os.getenv("BROKER_SECRET", "")
BIND = os.getenv("BROKER_BIND", "0.0.0.0")
PORT = int(os.getenv("BROKER_PORT", "9099"))
ALLOWED = {p.strip() for p in os.getenv("BROKER_PLATFORMS", "youtube").split(",") if p.strip()}
DB = os.getenv("POSTIZ_DB_CONTAINER", "postiz-db")
APP = os.getenv("POSTIZ_CONTAINER", "postiz")


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout or ""
    except Exception:
        return ""


def token_for(platform: str) -> dict | None:
    if platform not in ALLOWED:
        return None
    sql = (
        "SELECT token, \"refreshToken\", \"tokenExpiration\" FROM \"Integration\" "
        f"WHERE \"providerIdentifier\"='{platform}' AND \"deletedAt\" IS NULL "
        "ORDER BY \"updatedAt\" DESC LIMIT 1"
    )
    out = _run(["docker", "exec", DB, "psql", "-U", "postiz", "-d", "postiz",
                "-t", "-A", "-F", "\t", "-c", sql]).strip()
    if not out:
        return None
    parts = out.splitlines()[0].split("\t")
    env = _run(["docker", "exec", APP, "env"])
    cid = csec = ""
    prefix = platform.upper()
    for line in env.splitlines():
        if line.startswith(f"{prefix}_CLIENT_ID="):
            cid = line.split("=", 1)[1]
        elif line.startswith(f"{prefix}_CLIENT_SECRET="):
            csec = line.split("=", 1)[1]
    return {
        "platform": platform,
        "token": parts[0] if len(parts) > 0 else "",
        "refresh_token": parts[1] if len(parts) > 1 else "",
        "expires_at": parts[2] if len(parts) > 2 else "",
        "client_id": cid,
        "client_secret": csec,
    }


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        if not SECRET or self.headers.get("X-Broker-Secret") != SECRET:
            return self._json(401, {"error": "unauthorized"})
        if u.path != "/health" and u.path != "/token":
            return self._json(404, {"error": "not found"})
        if u.path == "/health":
            return self._json(200, {"ok": True})
        platform = (parse_qs(u.query).get("platform") or [""])[0]
        data = token_for(platform)
        if not data:
            return self._json(404, {"error": f"no token for {platform}"})
        return self._json(200, data)

    def log_message(self, *args):  # silence
        return


def main() -> int:
    if not SECRET:
        print("BROKER_SECRET is required", file=sys.stderr)
        return 2
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"token broker on {BIND}:{PORT} platforms={sorted(ALLOWED)}", file=sys.stderr)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
