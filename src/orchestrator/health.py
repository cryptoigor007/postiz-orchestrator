from __future__ import annotations
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable

logger = logging.getLogger(__name__)


def start_health_server(port: int, get_status: Callable[[], dict[str, Any]]) -> HTTPServer | None:
    if port <= 0:
        return None

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path not in ("/health", "/", "/metrics"):
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(get_status()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
    except OSError as e:
        logger.warning("Health server not started: %s", e)
        return None

    t = threading.Thread(target=server.serve_forever, name="health", daemon=True)
    t.start()
    logger.info("Health server on :%s", port)
    return server
