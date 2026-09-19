from __future__ import annotations
import sys
from pathlib import Path

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
