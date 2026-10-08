"""Unit B2 media host (P6.1) — dry-run + mock."""

from __future__ import annotations

import httpx

from orchestrator.media_host.b2 import B2MediaHost, create_media_host


def test_dry_run_upload(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"fake")
    h = create_media_host(dry_run=True, bucket_name="media-tmp")
    url = h.upload(f)
    assert url.startswith("https://")
    assert "media-tmp" in url
    assert h.cleanup_all() >= 1


def test_not_configured():
    h = B2MediaHost(key_id="", app_key="", dry_run=False)
    assert h.configured is False


def test_authorize_mock():
    def handler(request: httpx.Request) -> httpx.Response:
        if "b2_authorize_account" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "authorizationToken": "tok",
                    "apiUrl": "https://api.example",
                    "downloadUrl": "https://f000.example",
                },
            )
        return httpx.Response(404)

    h = B2MediaHost(
        key_id="k",
        app_key="s",
        bucket_id="b",
        bucket_name="bn",
        transport=httpx.MockTransport(handler),
    )
    auth = h.authorize()
    assert auth["authorizationToken"] == "tok"
