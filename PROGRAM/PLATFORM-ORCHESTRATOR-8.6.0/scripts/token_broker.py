#!/usr/bin/env python3
"""Orchestrator-local OAuth token broker (platform-zero C1).

Serves platform tokens from local JSON files under TOKENS_DIR — no docker,
no platform Postgres, no platform containers.

Env:
  BROKER_SECRET      shared secret (required)
  BROKER_BIND        bind address (default 127.0.0.1)
  BROKER_PORT        port (default 9099)
  BROKER_PLATFORMS   comma list allowed (default youtube)
  BROKER_ALLOW_IPS   optional IP allowlist (empty = all, still need secret)
  TOKENS_DIR         directory with <platform>.json files
                     (default: /opt/orchestrator/tokens)
  BROKER_UPLOADS_DIR local media staging dir for /symlink (optional)
  BROKER_FRONTEND_URL public base for media URLs from /symlink
  BROKER_SRC_PREFIX  allowed source prefix for /symlink (default /mnt/video/)
  BROKER_SRC_HOST_PREFIX host-side path mapping for /symlink

Token file format (tokens/<platform>.json, mode 600):
  {
    "access_token": "...",
    "refresh_token": "...",
    "expires_at": 1234567890.0,
    "token_type": "Bearer",
    "scope": "...",
    "client_id": "..."
  }

Optional multi-account: tokens/<platform>__<account_id>.json
  GET /token?platform=youtube&id=ACC1  → tokens/youtube__ACC1.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SECRET = os.getenv("BROKER_SECRET", "")
BIND = os.getenv("BROKER_BIND", "127.0.0.1")
PORT = int(os.getenv("BROKER_PORT", "9099"))
ALLOWED = {p.strip() for p in os.getenv("BROKER_PLATFORMS", "youtube").split(",") if p.strip()}
ALLOW_IPS = {x.strip() for x in os.getenv("BROKER_ALLOW_IPS", "").split(",") if x.strip()}
TOKENS_DIR = Path(os.getenv("TOKENS_DIR", "/opt/orchestrator/tokens"))
UPLOADS = os.getenv("BROKER_UPLOADS_DIR", "")
FRONTEND = os.getenv("BROKER_FRONTEND_URL", "").rstrip("/")
SRC_PREFIX = os.getenv("BROKER_SRC_PREFIX", "/mnt/video/")
HOST_PREFIX = os.getenv("BROKER_SRC_HOST_PREFIX", "/mnt/media/")

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def ip_allowed(ip: str, allowed: set[str] | None = None) -> bool:
    allowed = ALLOW_IPS if allowed is None else allowed
    return (not allowed) or ip in allowed or ip in ("127.0.0.1", "::1")


def _safe_platform(platform: str) -> str:
    p = (platform or "").strip().lower()
    if not _SAFE_ID.fullmatch(p):
        raise ValueError(f"invalid platform: {platform!r}")
    return p


def _safe_account_id(account_id: str | None) -> str | None:
    if not account_id:
        return None
    a = account_id.strip()
    if not _SAFE_ID.fullmatch(a):
        raise ValueError(f"invalid account_id: {account_id!r}")
    return a


def token_file_path(platform: str, account_id: str | None = None) -> Path:
    """Resolve tokens/<platform>.json or tokens/<platform>__<id>.json."""
    p = _safe_platform(platform)
    aid = _safe_account_id(account_id)
    name = f"{p}__{aid}.json" if aid else f"{p}.json"
    path = (TOKENS_DIR / name).resolve()
    if not str(path).startswith(str(TOKENS_DIR.resolve())):
        raise ValueError("token path escapes TOKENS_DIR")
    return path


def load_token_file(platform: str, account_id: str | None = None) -> dict | None:
    """Load token JSON from local file. Returns None if missing/invalid."""
    try:
        path = token_file_path(platform, account_id)
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    access = str(raw.get("access_token") or raw.get("token") or "")
    if not access:
        return None
    return {
        "platform": platform,
        "token": access,
        "refresh_token": str(raw.get("refresh_token") or ""),
        "expires_at": raw.get("expires_at") if raw.get("expires_at") is not None else "",
        "client_id": str(raw.get("client_id") or ""),
        "token_type": str(raw.get("token_type") or "Bearer"),
        "scope": str(raw.get("scope") or ""),
    }


def token_for(platform: str, integration_id: str | None = None) -> dict | None:
    """Return token payload for platform[/account]. No docker, no platform DB."""
    if platform not in ALLOWED:
        return None
    try:
        _safe_platform(platform)
        if integration_id:
            _safe_account_id(integration_id)
    except ValueError:
        return None
    return load_token_file(platform, integration_id)


def build_token_sql(platform: str, integration_id: str | None = None) -> str:
    """Deprecated: platform SQL removed. Validates ids and returns a marker string.

    Kept so existing unit tests that only check id sanitization still import.
    Raises ValueError on invalid platform/integration_id (same as before).
    """
    p = _safe_platform(platform)
    if integration_id:
        aid = _safe_account_id(integration_id)
        return f"local-file:{p}__{aid}"
    return f"local-file:{p}"


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
        """Optional local symlink helper (no platform volume required)."""
        import datetime as _dt
        import uuid as _uuid
        from pathlib import Path as _Path

        if not UPLOADS:
            return {"error": "BROKER_UPLOADS_DIR not configured"}
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
        return {
            "media_id": _uuid.uuid4().hex,
            "rel": rel,
            "path": (FRONTEND + rel) if FRONTEND else rel,
        }

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
            return self._json(200, {
                "ok": True,
                "tokens_dir": str(TOKENS_DIR),
                "platforms": sorted(ALLOWED),
                "backend": "local-files",
            })
        platform = (parse_qs(u.query).get("platform") or [""])[0]
        integration_id = (parse_qs(u.query).get("id") or [""])[0] or None
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
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    print(
        f"token broker on {BIND}:{PORT} platforms={sorted(ALLOWED)} "
        f"tokens_dir={TOKENS_DIR} backend=local-files",
        file=sys.stderr,
    )
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
