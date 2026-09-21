from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def start_http_server(
    port: int,
    get_health: Callable[[], dict[str, Any]],
    webapp_handler: Callable[[str, str, dict, bytes], tuple[int, Any, str]] | None = None,
) -> ThreadingHTTPServer | None:
    if port <= 0:
        return None

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: Any, ctype: str) -> None:
            if isinstance(payload, (dict, list)):
                body = json.dumps(payload, ensure_ascii=False).encode()
                ctype = "application/json; charset=utf-8"
            elif isinstance(payload, bytes):
                body = payload
                ctype = ctype
            else:
                body = str(payload).encode()
                ctype = ctype or "text/plain; charset=utf-8"
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            # Q: CORS — only same-origin by default; allow explicit ORCH_CORS_ORIGIN
            import os as _os
            cors = _os.getenv("ORCH_CORS_ORIGIN", "").strip()
            if cors:
                self.send_header("Access-Control-Allow-Origin", cors)
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Webapp-Key, X-Health-Token, Authorization")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            if ctype.startswith("image/"):
                # обложки/кадры — статичные: кэшируем, чтобы не «моргали» при перерисовке
                self.send_header("Cache-Control", "public, max-age=604800, immutable")
            else:
                self.send_header("Cache-Control", "no-store")
            if "html" in (ctype or ""):
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'",
                )
            self.end_headers()
            self.wfile.write(body)

        def _headers_dict(self) -> dict[str, str]:
            return {k: v for k, v in self.headers.items()}

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/health", "/metrics", "/"):
                # S18: optional token for metrics; /health stays open for probes if no token set
                token = os.getenv("ORCH_HEALTH_TOKEN", "").strip()
                if token and path != "/health":
                    provided = (
                        self.headers.get("X-Health-Token")
                        or self.headers.get("Authorization")
                        or ""
                    )
                    if provided.startswith("Bearer "):
                        provided = provided[7:]
                    import hmac
                    if not hmac.compare_digest(provided, token):
                        self._send(401, {"error": "unauthorized"}, "application/json")
                        return
                self._send(200, get_health(), "application/json")
                return
            if webapp_handler and path.startswith("/webapp"):
                code, payload, ctype = webapp_handler("GET", self.path, self._headers_dict(), b"")
                self._send(code, payload, ctype)
                return
            self._send(404, {"error": "not found"}, "application/json")

        def do_OPTIONS(self):  # noqa: N802
            self.send_response(204)
            import os as _os
            cors = _os.getenv("ORCH_CORS_ORIGIN", "").strip()
            if cors:
                self.send_header("Access-Control-Allow-Origin", cors)
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Webapp-Key, X-Health-Token, Authorization")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()

        def do_POST(self):  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            if webapp_handler and path.startswith("/webapp"):
                code, payload, ctype = webapp_handler("POST", self.path, self._headers_dict(), body)
                self._send(code, payload, ctype)
                return
            self._send(404, {"error": "not found"}, "application/json")

        def log_message(self, fmt, *args):
            logger.debug("http: " + fmt, *args)

    try:
        # S18: bind configurable; default 127.0.0.1 for safety, 0.0.0.0 only if set
        bind = os.getenv("ORCH_HTTP_BIND", "127.0.0.1").strip() or "127.0.0.1"
        server = ThreadingHTTPServer((bind, port), Handler)
    except OSError as e:
        logger.warning("HTTP server not started: %s", e)
        return None

    t = threading.Thread(target=server.serve_forever, name="http", daemon=True)
    t.start()
    logger.info("HTTP server on %s:%s (health + webapp)", bind, port)
    return server
