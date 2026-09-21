from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.http_server import start_http_server


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _raw(port: int, request: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
        s.sendall(request)
        s.settimeout(5)
        try:
            return s.recv(512)
        except TimeoutError:
            return b""


def test_bad_content_length_rejected():
    """P2-5: Content-Length: -1/abc не должен вешать поток до аутентификации."""
    port = _free_port()
    srv = start_http_server(
        port,
        lambda: {"ok": True},
        lambda *a: (200, {"ok": True}, "application/json"),
    )
    assert srv is not None
    try:
        head = b"POST /webapp/api/status HTTP/1.1\r\nHost: x\r\nContent-Length: -1\r\n\r\n"
        resp = _raw(port, head)
        assert b"400" in resp.split(b"\r\n", 1)[0], resp[:60]
        head2 = b"POST /webapp/api/status HTTP/1.1\r\nHost: x\r\nContent-Length: abc\r\n\r\n"
        resp2 = _raw(port, head2)
        assert b"400" in resp2.split(b"\r\n", 1)[0], resp2[:60]
    finally:
        srv.shutdown()
