from __future__ import annotations

import httpx
import pytest

from orchestrator.http_client import ModuleHttpClient


def test_http_boundary_injects_request_and_correlation_ids():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request_id"] = request.headers.get("X-Request-Id")
        seen["correlation_id"] = request.headers.get("X-Correlation-Id")
        return httpx.Response(200, json={"ok": True}, request=request)

    client = ModuleHttpClient(
        platform="c11-test",
        max_retries=1,
        transport=httpx.MockTransport(handler),
    )
    response = client.request("GET", "https://api.example.test/v1/ping")
    assert response.status_code == 200
    assert seen["request_id"]
    assert seen["request_id"] == seen["correlation_id"]


def test_http_boundary_enforces_optional_host_allowlist():
    client = ModuleHttpClient(
        platform="c11-test",
        max_retries=1,
        allowed_hosts={"allowed.example.test"},
        transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request)),
    )
    assert client.request("GET", "https://allowed.example.test/ok").status_code == 200
    with pytest.raises(ValueError, match="HTTP host not allowed"):
        client.request("GET", "https://blocked.example.test/deny")


def test_http_boundary_rejects_non_http_urls():
    client = ModuleHttpClient(platform="c11-test", max_retries=1)
    with pytest.raises(ValueError, match="unsafe HTTP URL"):
        client.request("GET", "file:///tmp/secret")
