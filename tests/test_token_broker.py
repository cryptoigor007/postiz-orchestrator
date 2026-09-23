from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.engines.token_broker_client import TokenBrokerClient


def test_token_broker_client_request_shape():
    calls = []

    def http(method, url, params, headers):
        calls.append((method, url, params, headers))
        return {"token": "TOK", "client_id": "cid", "client_secret": "sec",
                "refresh_token": "rt", "expires_at": "2026-09-19T12:00:00Z"}

    c = TokenBrokerClient("http://host:9000/", "S3CRET", http=http)
    r = c.get("youtube")
    assert r["token"] == "TOK"
    assert calls[0][0] == "GET"
    assert calls[0][1] == "http://host:9000/token"
    assert calls[0][2] == {"platform": "youtube"}
    assert calls[0][3]["X-Broker-Secret"] == "S3CRET"


def test_token_broker_error_message(monkeypatch):
    import io
    import urllib.error
    import urllib.request

    import pytest

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 404, "Not Found", {},
            io.BytesIO(b'{"error":"no token for youtube"}'))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="token broker"):
        TokenBrokerClient("http://x:9099", "s").get("youtube")


def test_token_broker_passes_integration_id():
    calls = []
    def http(method, url, params, headers):
        calls.append(params)
        return {"token": "T"}
    c = TokenBrokerClient("http://b", "s", http=http)
    c.get("youtube", "INT1")
    assert calls[0] == {"platform": "youtube", "id": "INT1"}
    c.get("youtube")
    assert calls[1] == {"platform": "youtube"}


def test_broker_sql_has_channel_filter():
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import token_broker as tb
    assert "\"id\"='INT1'" in tb.build_token_sql("youtube", "INT1")
    assert "\"id\"=" not in tb.build_token_sql("youtube", None)
    # P2-8: невалидный id — ошибка, а не запрос без фильтра (токен чужого канала)
    with pytest.raises(ValueError):
        tb.build_token_sql("youtube", "bad';drop")
