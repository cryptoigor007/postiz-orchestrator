from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace


def test_cover_thumb_requires_header_and_not_query_key(tmp_path, monkeypatch):
    from orchestrator.db import Database
    from orchestrator.config import load_config
    from orchestrator.webapp_api import WebAppAPI
    monkeypatch.setenv("WEBAPP_ACCESS_KEY", "secret-key")
    monkeypatch.delenv("WEBAPP_DEV", raising=False)
    root = tmp_path / "media"
    root.mkdir()
    img = root / "c.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 40)
    cfg = load_config(Path("config.ci.yaml"))
    db = Database(tmp_path / "wa.sqlite")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    monkeypatch.setenv("WEBAPP_BROWSE_ROOT", str(root))
    api = WebAppAPI({"cfg": cfg, "db": db})
    code, _, _ = api.handle("GET", f"/webapp/api/cover/thumb?key=secret-key&path={img}", {}, b"")
    assert code == 401
    code, blob, _ = api.handle("GET", f"/webapp/api/cover/thumb?path={img}", {"X-Webapp-Key":"secret-key"}, b"")
    assert code == 200 and blob.startswith(b"\x89PNG")


def test_cover_thumb_frontend_has_no_query_access_key():
    s = Path("webapp/app.js").read_text()
    assert "cover/thumb?key=" not in s
    assert "data-thumb-path" in s
    assert "X-Webapp-Key" in s


def test_facebook_remote_page_surfaces_partial_scheduled_error(monkeypatch):
    from orchestrator.platforms.facebook.module import FacebookModule
    m = FacebookModule.__new__(FacebookModule)
    m._api = SimpleNamespace(
        list_videos=lambda limit: [{"id":"v1","title":"Video","permalink_url":"u","created_time":"t"}],
        list_scheduled_posts=lambda limit: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    page = m.list_remote_items(limit=10)
    assert page.partial is True
    assert any("scheduled inventory request failed" in n for n in page.notes)
    assert len(page.items) == 1


def test_x_remote_inventory_is_explicitly_partial():
    from orchestrator.platforms.x.module import XModule
    m = XModule.__new__(XModule)
    page = m.list_remote_items(limit=10)
    assert page.partial is True
    assert page.items == []
    assert "not authoritative" in page.notes[0]


def test_queue_busy_has_explicit_retry_schedule():
    s = Path("src/orchestrator/publisher.py").read_text()
    assert "provider account queue busy; retry scheduled" in s
    assert "next_retry_at" in s
    assert "timedelta(seconds=30)" in s
