#!/usr/bin/env python3
"""Postiz OAuth token broker (runs on the Postiz VM).

Reads a platform channel token from the Postiz DB (via docker exec) and serves
it over HTTP to the orchestrator (which cannot reach the docker network).

Env:
  BROKER_SECRET      shared secret (required)
  BROKER_BIND        bind address (default 0.0.0.0)
  BROKER_PORT        port (default 9099)
  BROKER_PLATFORMS   comma list allowed (default youtube)
  BROKER_UPLOADS_DIR Postiz uploads dir (default docker volume _data path)
  BROKER_FRONTEND_URL public base of Postiz (for media URLs)
  BROKER_SRC_PREFIX  allowed source prefix (default /mnt/video/)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SECRET = os.getenv("BROKER_SECRET", "")
BIND = os.getenv("BROKER_BIND", "0.0.0.0")
PORT = int(os.getenv("BROKER_PORT", "9099"))
ALLOWED = {p.strip() for p in os.getenv("BROKER_PLATFORMS", "youtube").split(",") if p.strip()}
ALLOW_IPS = {x.strip() for x in os.getenv("BROKER_ALLOW_IPS", "").split(",") if x.strip()}
UPLOADS = os.getenv("BROKER_UPLOADS_DIR",
                    "/var/lib/docker/volumes/postiz_postiz_uploads/_data")
FRONTEND = os.getenv("BROKER_FRONTEND_URL", "").rstrip("/")
SRC_PREFIX = os.getenv("BROKER_SRC_PREFIX", "/mnt/video/")
HOST_PREFIX = os.getenv("BROKER_SRC_HOST_PREFIX", "/mnt/media/")
DB = os.getenv("POSTIZ_DB_CONTAINER", "postiz-db")
APP = os.getenv("POSTIZ_CONTAINER", "postiz")


def ip_allowed(ip: str, allowed: set[str] | None = None) -> bool:
    allowed = ALLOW_IPS if allowed is None else allowed
    return (not allowed) or ip in allowed or ip in ("127.0.0.1", "::1")


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout or ""
    except Exception:
        return ""


def build_token_sql(platform: str, integration_id: str | None = None) -> str:
    """Build SELECT for Postiz Integration row (S8: no free-form SQL injection)."""
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9_-]+", platform or ""):
        raise ValueError(f"invalid platform for SQL: {platform!r}")
    sql = (
        'SELECT token, "refreshToken", "tokenExpiration" FROM "Integration" '
        "WHERE \"providerIdentifier\"='" + platform + "' AND \"deletedAt\" IS NULL "
    )
    if integration_id:
        if not _re.fullmatch(r"[A-Za-z0-9_-]+", integration_id):
            # P2-8: раньше возвращался SQL БЕЗ фильтра → отдавался токен самого свежего
            # канала платформы (чужого), а не ошибка.
            raise ValueError(f"invalid integration_id: {integration_id!r}")
        sql += "AND \"id\"='" + integration_id + "' "
    return sql + 'ORDER BY "updatedAt" DESC LIMIT 1'


def token_for(platform: str, integration_id: str | None = None) -> dict | None:
    if platform not in ALLOWED:
        return None
    try:
        sql = build_token_sql(platform, integration_id)
    except ValueError:
        return None
    out = _run(["docker", "exec", DB, "psql", "-U", "postiz", "-d", "postiz",
                "-t", "-A", "-F", "\t", "-c", sql]).strip()
    if not out:
        return None
    parts = out.splitlines()[0].split("\t")
    env = _run(["docker", "exec", APP, "env"])
    cid = ""
    prefix = platform.upper()
    for line in env.splitlines():
        if line.startswith(f"{prefix}_CLIENT_ID="):
            cid = line.split("=", 1)[1]
    # Never expose client_secret over the broker API (S5).
    return {
        "platform": platform,
        "token": parts[0] if len(parts) > 0 else "",
        "refresh_token": parts[1] if len(parts) > 1 else "",
        "expires_at": parts[2] if len(parts) > 2 else "",
        "client_id": cid,
    }


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self) -> bool:
        import hmac
        if not ip_allowed(self.client_address[0]):
            self._json(403, {"error": "forbidden"})
            return False
        provided = self.headers.get("X-Broker-Secret") or ""
        if not SECRET or not hmac.compare_digest(provided, SECRET):
            self._json(401, {"error": "unauthorized"})
            return False
        return True

    def _symlink(self, src: str, name: str = "") -> dict:
        import datetime as _dt
        import uuid as _uuid
        from pathlib import Path as _Path
        try:
            src_resolved = _Path(src).resolve()
            prefix_resolved = _Path(SRC_PREFIX).resolve()
        except Exception as e:
            return {"error": f"bad path: {e}"}
        try:
            if not (src_resolved == prefix_resolved or src_resolved.is_relative_to(prefix_resolved)):
                return {"error": f"src must be under {SRC_PREFIX}"}
        except (ValueError, TypeError):
            return {"error": f"src must be under {SRC_PREFIX}"}
        host_src = str(src_resolved)
        if HOST_PREFIX:
            rel = str(src_resolved)[len(str(prefix_resolved)):].lstrip("/")
            try:
                host_src = str((_Path(HOST_PREFIX).resolve() / rel).resolve())
            except Exception:
                host_src = str(src_resolved)
        if not os.path.isfile(host_src):
            if not os.path.isfile(str(src_resolved)):
                return {"error": f"src not found ({host_src})"}
            host_src = str(src_resolved)
        verified_target = host_src
        base = os.path.basename(name or src)
        safe = "".join(c for c in base if c.isalnum() or c in "._- ").strip() or "media.mp4"
        now = _dt.date.today()
        rel_dir = now.strftime("%Y/%m/%d")
        target_dir = os.path.join(UPLOADS, rel_dir)
        os.makedirs(target_dir, exist_ok=True)
        uniq = _uuid.uuid4().hex * 2
        fname = f"{uniq[:32]}{os.path.splitext(safe)[1] or '.mp4'}"
        link_path = os.path.join(target_dir, fname)
        try:
            if os.path.islink(link_path) or os.path.exists(link_path):
                os.unlink(link_path)
            os.symlink(verified_target, link_path)
        except Exception as e:
            return {"error": f"symlink failed: {e}"}
        rel = f"/uploads/{rel_dir}/{fname}"
        return {"media_id": _uuid.uuid4().hex, "rel": rel,
                "path": (FRONTEND + rel) if FRONTEND else rel}

    def do_POST(self):  # noqa: N802
        u = urlparse(self.path)
        if not self._auth():
            return
        if u.path != "/symlink":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"error": "bad json"})
        src = str(data.get("src") or "")
        res = self._symlink(src, str(data.get("name") or ""))
        if "error" in res:
            return self._json(400, res)
        return self._json(200, res)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        if not self._auth():
            return
        if u.path != "/health" and u.path != "/token":
            return self._json(404, {"error": "not found"})
        if u.path == "/health":
            return self._json(200, {"ok": True})
        platform = (parse_qs(u.query).get("platform") or [""])[0]
        integration_id = (parse_qs(u.query).get("id") or [""])[0]
        data = token_for(platform, integration_id)
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
