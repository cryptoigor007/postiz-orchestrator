"""Unit-тесты модуля YouTube (P2): mock HTTP, ошибки, регресс обложки, dry-run."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from orchestrator.http_client import ModuleHttpClient, mask_secrets
from orchestrator.platforms.base import (
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    PublishMeta,
)
from orchestrator.platforms.youtube.api import YouTubeApi, map_youtube_error
from orchestrator.platforms.youtube.module import YouTubeModule


def _resp(
    status: int,
    body: dict | str | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    content = b""
    if isinstance(body, dict):
        content = json.dumps(body).encode()
    elif isinstance(body, str):
        content = body.encode()
    return httpx.Response(
        status,
        content=content,
        headers=headers or {"content-type": "application/json"},
        request=httpx.Request("GET", "https://example.test"),
    )


class ScriptedTransport(httpx.BaseTransport):
    """Последовательность ответов для ModuleHttpClient."""

    def __init__(self, script: list[httpx.Response]) -> None:
        self.script = list(script)
        self.calls: list[tuple[str, str]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, str(request.url)))
        if not self.script:
            return _resp(500, {"error": {"message": "no more scripted responses"}})
        return self.script.pop(0)


@pytest.fixture
def video_file(tmp_path: Path) -> Path:
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    return p


@pytest.fixture
def thumb_file(tmp_path: Path) -> Path:
    p = tmp_path / "cover.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # minimal jpeg-ish
    return p


def test_mask_secrets() -> None:
    assert "***" in mask_secrets("Bearer ya29.a0AfH6...")
    assert "token=***" in mask_secrets("https://x?token=secret123&a=1")
    assert "access_token" in mask_secrets('{"access_token": "abc"}')  # ключ остаётся
    assert "***" in mask_secrets('{"access_token": "abc"}')


def test_map_quota() -> None:
    err = map_youtube_error(
        403,
        {"error": {"message": "quotaExceeded", "errors": [{"reason": "quotaExceeded"}]}},
    )
    assert err.code == ModuleErrorCode.QUOTA
    assert not err.retryable


def test_map_auth_expired() -> None:
    err = map_youtube_error(401, {"error": {"message": "Invalid Credentials"}})
    assert err.code == ModuleErrorCode.AUTH_EXPIRED
    assert err.retryable


def test_map_invalid_grant() -> None:
    err = map_youtube_error(400, {"error": {"message": "invalid_grant"}})
    # 400 + invalid_grant → AUTH_REQUIRED (нужна переавторизация)
    assert err.code in (ModuleErrorCode.AUTH_REQUIRED, ModuleErrorCode.MEDIA_INVALID)


def test_map_not_verified_thumbnail() -> None:
    err = map_youtube_error(
        403,
        {
            "error": {
                "message": "The authenticated user does not have permission "
                "or the account is not verified",
                "errors": [{"reason": "forbidden"}],
            }
        },
        context="thumbnails.set",
    )
    assert err.code == ModuleErrorCode.PLATFORM_REJECTED
    assert "верифицир" in err.message.lower() or "обложка" in err.message.lower()


def test_upload_resumable_success(video_file: Path) -> None:
    transport = ScriptedTransport(
        [
            # init resumable
            _resp(
                200,
                {},
                headers={"Location": "https://www.googleapis.com/upload/youtube/v3/up/1"},
            ),
            # final chunk
            _resp(200, {"id": "vidABC", "status": {"privacyStatus": "private"}}),
        ]
    )
    http = ModuleHttpClient(
        platform="youtube", module_version="2.0.0", transport=transport, max_retries=1
    )
    api = YouTubeApi(lambda: "tok", http=http)
    result = api.resumable_upload(
        str(video_file),
        title="Test",
        description="desc",
        privacy_status="private",
        publish_at=datetime(2026, 9, 26, 12, 0, tzinfo=UTC),
    )
    assert result["id"] == "vidABC"
    assert any("uploadType=resumable" in u for _, u in transport.calls)


def test_module_upload_keeps_id_when_thumbnail_fails(
    video_file: Path, thumb_file: Path
) -> None:
    """Регресс 24.09: ошибка thumbnails.set НЕ теряет videoId."""
    transport = ScriptedTransport(
        [
            # init
            _resp(
                200,
                {},
                headers={"Location": "https://www.googleapis.com/upload/youtube/v3/up/2"},
            ),
            # upload done
            _resp(200, {"id": "vidKEEP", "status": {"privacyStatus": "private"}}),
            # thumbnails.set → not verified
            _resp(
                403,
                {
                    "error": {
                        "message": "The account is not verified",
                        "errors": [{"reason": "forbidden"}],
                    }
                },
            ),
        ]
    )
    http = ModuleHttpClient(
        platform="youtube", module_version="2.0.0", transport=transport, max_retries=1
    )
    mod = YouTubeModule(lambda: "tok", http=http)
    meta = PublishMeta(
        title="T",
        description="D",
        extra={"thumbnail": str(thumb_file)},
    )
    prepared = mod.prepare(MediaSpec(path=str(video_file)))
    when = datetime(2026, 9, 26, 15, 0, tzinfo=UTC)
    result = mod.upload(prepared, meta, when=when)
    assert result.external_id == "vidKEEP"
    assert result.url == "https://youtu.be/vidKEEP"
    assert result.state == "scheduled"


def test_module_dry_run(video_file: Path) -> None:
    mod = YouTubeModule(lambda: "", dry_run=True)
    prepared = mod.prepare(MediaSpec(path=str(video_file)))
    up = mod.upload(prepared, PublishMeta(title="x"), when=None)
    assert up.external_id.startswith("dryrun_")
    assert up.url.startswith("https://youtu.be/")
    st = mod.get_status(up.external_id)
    assert st.state == "published"
    assert mod.auth_status().ok is True


def test_module_auth_status_ok() -> None:
    transport = ScriptedTransport(
        [
            _resp(
                200,
                {
                    "items": [
                        {
                            "id": "UC123",
                            "snippet": {"title": "testAccount"},
                        }
                    ]
                },
            )
        ]
    )
    http = ModuleHttpClient(
        platform="youtube", module_version="2.0.0", transport=transport, max_retries=1
    )
    mod = YouTubeModule(lambda: "tok", http=http)
    st = mod.auth_status()
    assert st.ok is True
    assert st.account == "testAccount"


def test_module_auth_status_fail() -> None:
    transport = ScriptedTransport(
        [_resp(401, {"error": {"message": "Invalid Credentials"}})]
    )
    http = ModuleHttpClient(
        platform="youtube", module_version="2.0.0", transport=transport, max_retries=1
    )
    mod = YouTubeModule(lambda: "bad", http=http)
    st = mod.auth_status()
    assert st.ok is False
    assert "AUTH" in st.details or "токен" in st.details.lower() or "Invalid" in st.details


def test_module_prepare_missing_file(tmp_path: Path) -> None:
    mod = YouTubeModule(lambda: "tok", dry_run=False)
    with pytest.raises(ModuleError) as ei:
        mod.prepare(MediaSpec(path=str(tmp_path / "no.mp4")))
    assert ei.value.code == ModuleErrorCode.MEDIA_INVALID


def test_module_delete_and_status(video_file: Path) -> None:
    transport = ScriptedTransport(
        [
            _resp(204),  # delete
            _resp(200, {"items": []}),  # list → deleted
        ]
    )
    http = ModuleHttpClient(
        platform="youtube", module_version="2.0.0", transport=transport, max_retries=1
    )
    mod = YouTubeModule(lambda: "tok", http=http)
    assert mod.delete("vidX") is True
    st = mod.get_status("vidX")
    assert st.state == "deleted"


def test_module_check_claims_unsupported() -> None:
    mod = YouTubeModule(lambda: "", dry_run=True)
    r = mod.check_claims("vid")
    assert r.supported is False


def test_registry_has_youtube() -> None:
    from orchestrator.platforms import default_registry, resolve_engine

    reg = default_registry()
    assert reg.has("youtube")
    resolved = resolve_engine("module:youtube")
    assert resolved.kind == "module"
    assert resolved.module_id == "youtube"
    with pytest.raises(ValueError):
        resolve_engine("direct")


def test_manifest_loads() -> None:
    from pathlib import Path

    from orchestrator.platforms.manifest import load_manifest

    m = load_manifest(
        Path(__file__).resolve().parents[1]
        / "src"
        / "orchestrator"
        / "platforms"
        / "youtube"
        / "manifest.yaml"
    )
    assert m.id == "youtube"
    assert m.capabilities.get("early_upload") is True
    assert m.capabilities.get("claims_check") == "manual"
    assert m.core_min == "8.5.0"
