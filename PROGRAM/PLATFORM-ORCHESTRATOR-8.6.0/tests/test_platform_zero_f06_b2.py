
"""F6: B2 streaming upload + delete(fileId, real fileName)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from orchestrator.media_host.b2 import B2MediaHost, CHUNK_SIZE


class _Router(httpx.MockTransport):
    def __init__(self):
        self.delete_bodies = []
        super().__init__(self._handler)

    def _handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "b2_authorize_account" in url:
            return httpx.Response(200, json={
                "authorizationToken": "tok",
                "apiUrl": "https://api.example",
                "downloadUrl": "https://dl.example",
            })
        if "b2_get_upload_url" in url:
            return httpx.Response(200, json={
                "uploadUrl": "https://upload.example/up",
                "authorizationToken": "uptok",
            })
        if "upload.example" in url:
            body = request.content
            return httpx.Response(200, json={
                "fileId": "fid123",
                "fileName": request.headers.get("X-Bz-File-Name", "x"),
            })
        if "b2_delete_file_version" in url:
            import json
            self.delete_bodies.append(json.loads(request.content.decode()))
            return httpx.Response(200, json={})
        return httpx.Response(404)


def test_upload_dry_run(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello" * 100)
    h = B2MediaHost(dry_run=True, bucket_name="b")
    url = h.upload(f)
    assert "dry.invalid" in url
    assert h._uploaded and h._uploaded[0][0].startswith("dry:")


def test_delete_sends_real_filename(tmp_path):
    router = _Router()
    h = B2MediaHost(
        key_id="k", app_key="s", bucket_id="bid", bucket_name="bn",
        transport=router, dry_run=False,
    )
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x" * 2048)
    url = h.upload(f, prefix="t")
    assert "dl.example" in url
    fid, fname = h._uploaded[0]
    assert fid == "fid123"
    assert h.delete(fid, fname) is True
    assert router.delete_bodies
    body = router.delete_bodies[0]
    assert body["fileId"] == "fid123"
    assert body["fileName"] != "x"  # not the old placeholder
    assert body["fileName"] == fname


def test_delete_without_name_uses_tracked(tmp_path):
    router = _Router()
    h = B2MediaHost(
        key_id="k", app_key="s", bucket_id="bid", bucket_name="bn",
        transport=router,
    )
    f = tmp_path / "v.mp4"
    f.write_bytes(b"y" * 100)
    h.upload(f)
    fid, fname = h._uploaded[0]
    assert h.delete(fid) is True  # name resolved from _uploaded
    assert router.delete_bodies[0]["fileName"] == fname
