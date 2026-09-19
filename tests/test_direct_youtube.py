from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.engines.direct_youtube import YouTubeEngine


class FakeHttp:
    """Records calls; returns canned YouTube API responses."""

    def __init__(self):
        self.calls = []

    def request(self, method, url, params=None, json=None, token=""):
        self.calls.append((method, url, params or {}, json, token))
        if url.endswith("/channels"):
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]}
        if url.endswith("/playlistItems"):
            return {"items": [{
                "snippet": {
                    "title": "My Video",
                    "description": "desc",
                    "publishedAt": "2026-09-10T10:00:00Z",
                    "thumbnails": {"high": {"url": "http://t"}},
                },
                "contentDetails": {"videoId": "vid1"},
            }]}
        if url.endswith("/videos") and method == "GET":
            return {"items": [{
                "id": "vid1",
                "snippet": {"title": "My Video", "description": "desc", "categoryId": "22"},
                "contentDetails": {"duration": "PT3M20S"},
                "status": {"privacyStatus": "public"},
            }]}
        if url.endswith("/videos") and method == "PUT":
            return {"items": [{"id": json["id"]}]}
        if url.endswith("/videos") and method == "DELETE":
            return {}
        return {}


def make():
    http = FakeHttp()
    eng = YouTubeEngine(token_provider=lambda: "TOKEN", http=http)
    return eng, http


def test_list_uploads_parses():
    eng, http = make()
    items = eng.list_uploads()
    assert len(items) == 1
    it = items[0]
    assert it["external_id"] == "vid1"
    assert it["title"] == "My Video"
    assert it["duration_sec"] == 200
    assert it["url"] == "https://www.youtube.com/watch?v=vid1"
    assert it["published_at"].startswith("2026-09-10")
    assert it["thumbnail_url"] == "http://t"
    # token passed through
    assert all(c[4] == "TOKEN" for c in http.calls)


def test_update_metadata_sends_description():
    eng, http = make()
    ok = eng.update_metadata("vid1", {"description": "new desc"})
    assert ok is True
    put = [c for c in http.calls if c[0] == "PUT"]
    assert put, "no PUT call"
    body = put[0][3]
    assert body["id"] == "vid1"
    assert body["snippet"]["description"] == "new desc"
    assert body["snippet"]["title"] == "My Video"  # preserved


def test_delete_and_claims():
    eng, http = make()
    assert eng.delete("vid1") is True
    assert any(c[0] == "DELETE" for c in http.calls)
    assert eng.check_claims("vid1")["status"] == "unknown"
    assert eng.capabilities()["update"] is True
