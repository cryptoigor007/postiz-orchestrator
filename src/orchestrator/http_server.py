from __future__ import annotations

import json
import logging
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
            if ctype.startswith("image/"):
                # обложки/кадры — статичные: кэшируем, чтобы не «моргали» при перерисовке
                self.send_header("Cache-Control", "public, max-age=604800, immutable")
            else:
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _headers_dict(self) -> dict[str, str]:
            return {k: v for k, v in self.headers.items()}

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/health", "/metrics", "/"):
                self._send(200, get_health(), "application/json")
                return
            if webapp_handler and path.startswith("/webapp"):
                code, payload, ctype = webapp_handler("GET", self.path, self._headers_dict(), b"")
                self._send(code, payload, ctype)
                return
            self._send(404, {"error": "not found"}, "application/json")

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
        server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    except OSError as e:
        logger.warning("HTTP server not started: %s", e)
        return None

    t = threading.Thread(target=server.serve_forever, name="http", daemon=True)
    t.start()
    logger.info("HTTP server on :%s (health + webapp)", port)
    return server
