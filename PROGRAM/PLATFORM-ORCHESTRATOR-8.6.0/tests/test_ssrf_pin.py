"""P0.1: SSRF cover/fetch — pin по IP (anti-rebinding), redirect-хопы, stream cap, hostname tricks."""
from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.webapp_api import (  # noqa: E402
    _fetch_image_pinned,
    _host_is_public,
    _hostname_ok,
    _resolve_and_pin,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


class FakeSock:
    """Мини-фейк сокета: отдаёт заранее заготовленный ответ (заголовки+тело)."""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
        self.closed = False

    def sendall(self, _b: bytes) -> None:
        pass

    def recv(self, n: int) -> bytes:
        if self._pos >= len(self._data):
            return b""
        out = self._data[self._pos:self._pos + n]
        self._pos += len(out)
        return out

    def close(self) -> None:
        self.closed = True


def _resp(status: int, headers: dict[str, str], body: bytes = b"") -> bytes:
    lines = [f"HTTP/1.1 {status} X"]
    lines += [f"{k}: {v}" for k, v in headers.items()]
    return ("\r\n".join(lines) + "\r\n\r\n").encode() + body


@pytest.fixture
def dns(monkeypatch):
    calls: list[tuple] = []

    def fake_getaddrinfo(host, port, **kw):
        calls.append((host, port))
        mapping = {"evil.example": ["93.184.216.34"], "pub.example": ["93.184.216.34"],
                   "private.example": ["10.0.0.5"], "mixed.example": ["93.184.216.34", "192.168.1.1"]}
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))
                for ip in mapping.get(host, [])]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    return calls


# --- _hostname_ok ---

@pytest.mark.parametrize("host", ["localhost", "foo.localhost", "x.local", "2130706433",
                                  "0x7f000001", "017700000001", "::1", "127.0.0.1", ""])
def test_hostname_tricks_rejected(host):
    assert _hostname_ok(host) is False


def test_hostname_ok_normal():
    assert _hostname_ok("example.com") is True
    assert _hostname_ok("sub.example.co.uk") is True


# --- _resolve_and_pin ---

def test_resolve_rejects_private_and_mixed(dns):
    with pytest.raises(ValueError):
        _resolve_and_pin("private.example")
    with pytest.raises(ValueError):
        _resolve_and_pin("mixed.example")  # хотя бы один приватный → отказ
    assert _resolve_and_pin("pub.example") == ["93.184.216.34"]


def test_host_is_public_compat(dns):
    assert _host_is_public("pub.example") is True
    assert _host_is_public("private.example") is False


# --- pin: коннект только к проверенному IP ---

def test_fetch_pins_validated_ip(monkeypatch, dns):
    seen: list[tuple] = []

    def fake_connect(addr, timeout=None):
        seen.append(addr)
        return FakeSock(_resp(200, {"Content-Type": "image/png",
                                    "Content-Length": str(len(PNG))}, PNG))

    monkeypatch.setattr(socket, "create_connection", fake_connect)
    blob, ctype, _final = _fetch_image_pinned("http://evil.example/pic.png")
    assert blob == PNG and ctype == "image/png"
    assert seen == [("93.184.216.34", 80)]  # ни разу не hostname → нет повторного resolve


def test_rebind_between_check_and_connect_blocked(monkeypatch):
    """DNS меняется на приватный после проверки: коннекта к приватному IP нет."""
    state = {"n": 0}

    def flip_getaddrinfo(host, port, **kw):
        state["n"] += 1
        ip = "93.184.216.34" if state["n"] == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", flip_getaddrinfo)
    connected: list = []
    monkeypatch.setattr(socket, "create_connection",
                        lambda a, timeout=None: (connected.append(a), FakeSock(_resp(
                            200, {"Content-Type": "image/png"}, PNG)))[1])
    blob, _c, _f = _fetch_image_pinned("http://evil.example/pic.png")
    assert blob == PNG
    # единственный коннект — на проверенный публичный IP
    assert connected == [("93.184.216.34", 80)]


def test_redirect_to_private_blocked(monkeypatch, dns):
    s1 = FakeSock(_resp(302, {"Location": "http://private.example/x.png"}))
    monkeypatch.setattr(socket, "create_connection", lambda a, timeout=None: s1)
    with pytest.raises(ValueError, match="not public"):
        _fetch_image_pinned("http://evil.example/pic.png")


def test_relative_redirect_same_host_ok(monkeypatch, dns):
    socks = [FakeSock(_resp(302, {"Location": "/other.png"})),
             FakeSock(_resp(200, {"Content-Type": "image/png",
                                  "Content-Length": str(len(PNG))}, PNG))]
    monkeypatch.setattr(socket, "create_connection", lambda a, timeout=None: socks.pop(0))
    blob, _c, final = _fetch_image_pinned("http://evil.example/pic.png")
    assert blob == PNG and final.endswith("/other.png")


def test_stream_oversize_capped(monkeypatch, dns):
    big = b"0" * 4096
    monkeypatch.setattr(socket, "create_connection",
                        lambda a, timeout=None: FakeSock(_resp(200, {"Content-Type": "image/png"}, big)))
    with pytest.raises(ValueError, match="too large"):
        _fetch_image_pinned("http://evil.example/pic.png", max_bytes=1024)


def test_content_length_oversize_rejected_before_body(monkeypatch, dns):
    monkeypatch.setattr(socket, "create_connection",
                        lambda a, timeout=None: FakeSock(_resp(
                            200, {"Content-Type": "image/png", "Content-Length": "99999999"}, b"")))
    with pytest.raises(ValueError, match="too large"):
        _fetch_image_pinned("http://evil.example/pic.png", max_bytes=1024)


@pytest.mark.parametrize("url", ["ftp://evil.example/x.png", "file:///etc/passwd",
                                 "http://user:pass@evil.example/x.png"])
def test_bad_scheme_and_userinfo_rejected(monkeypatch, dns, url):
    monkeypatch.setattr(socket, "create_connection",
                        lambda a, timeout=None: FakeSock(_resp(200, {})))
    with pytest.raises(ValueError):
        _fetch_image_pinned(url)


def test_decimal_ip_host_rejected(monkeypatch, dns):
    with pytest.raises(ValueError, match="not allowed"):
        _fetch_image_pinned("http://2130706433/x.png")
