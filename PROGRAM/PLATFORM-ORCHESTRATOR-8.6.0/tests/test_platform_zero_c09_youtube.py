"""platform-zero COMMIT 9: YouTube list_remote + 2 quota buckets; no cost_upload:1600."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.http_client import ModuleHttpClient  # noqa: E402
from orchestrator.platforms.manifest import load_manifest  # noqa: E402
from orchestrator.platforms.youtube.module import YouTubeModule  # noqa: E402


class _T(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "search" in url:
            return httpx.Response(200, json={
                "items": [{"id": {"videoId": "abc123"}, "snippet": {"title": "T"}}],
                "nextPageToken": None,
            })
        if "videos" in url:
            return httpx.Response(200, json={
                "items": [{
                    "id": "abc123",
                    "snippet": {"title": "T", "publishedAt": "2026-01-01T00:00:00Z"},
                    "status": {"privacyStatus": "private", "publishAt": "2026-03-10T16:00:00Z"},
                    "contentDetails": {},
                }],
            })
        return httpx.Response(404, json={"error": "no"})


def test_manifest_no_cost_upload_1600():
    m = load_manifest(ROOT / "src/orchestrator/platforms/youtube/manifest.yaml")
    q = m.limits.get("quota") or {}
    assert "cost_upload" not in q or q.get("cost_upload") != 1600
    assert "upload_bucket" in q
    assert q["upload_bucket"]["default_daily_limit"] == 100
    assert m.capabilities.get("scan_mode") == "auto"
    assert m.capabilities.get("list_uploads") is True


def test_get_quota_two_buckets():
    http = ModuleHttpClient(platform="youtube", module_version="2.2.0", transport=_T(), max_retries=1)
    mod = YouTubeModule(token_provider=lambda: "tok", http=http)
    q = mod.get_quota()
    assert "upload" in q.buckets
    assert "general" in q.buckets
    assert q.buckets["upload"]["limit"] == 100


def test_list_remote_items_maps_scheduled():
    http = ModuleHttpClient(platform="youtube", module_version="2.2.0", transport=_T(), max_retries=1)
    mod = YouTubeModule(token_provider=lambda: "tok", http=http)
    page = mod.list_remote_items(kinds={"scheduled", "private", "published"}, limit=10)
    assert any(i.external_id == "abc123" for i in page.items)
    it = next(i for i in page.items if i.external_id == "abc123")
    assert it.status == "scheduled"
    assert it.privacy == "private"
