from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.link_updater import LinkUpdater
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.telegram_bot import TelegramNotifier
from orchestrator.watcher import Watcher
from orchestrator.webapp_api import WEBAPP_BUILD, WebAppAPI

ROOT = Path(__file__).resolve().parents[1]


def test_db_settings_roundtrip(tmp_path):
    db = Database(tmp_path / "s.sqlite")
    assert db.get_setting("watch_roots") is None
    db.set_setting("watch_roots", '["/mnt/video"]')
    assert db.get_setting("watch_roots") == '["/mnt/video"]'
    db.set_setting("watch_roots", '["/other"]')
    assert db.get_setting("watch_roots") == '["/other"]'


def test_watcher_uses_db_roots(tmp_path):
    db = Database(tmp_path / "w.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))

    root = tmp_path / "videomaker"
    series = root / "Series 1"
    (series / "wide").mkdir(parents=True)
    (series / "wide" / "final_16x9.mp4").write_bytes(b"x")

    db.set_setting("watch_roots", json.dumps([str(root)]))
    # default roots point elsewhere and must be ignored
    w = Watcher(db, cfg, clock, ["/definitely/not/here"])
    total = 0
    for _ in range(3):
        total += w.scan()["long"]
    assert total == 1
    assert db.fetchone("SELECT id FROM long_videos WHERE folder_path=?", (str(series.resolve()),))


@pytest.fixture
def env(tmp_path):
    os.environ["WEBAPP_DEV"] = "1"
    os.environ["WEBAPP_BROWSE_ROOT"] = str(tmp_path)
    db = Database(tmp_path / "wa.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, postiz, clock, tg)
    watcher = Watcher(db, cfg, clock, [])
    comps = {
        "cfg": cfg, "db": db, "clock": clock, "safety": safety,
        "scheduler": sched, "link_upd": link, "publisher": pub,
        "watcher": watcher, "postiz": postiz,
    }
    return WebAppAPI(comps), db, clock, cfg, watcher


def test_api_roots_get_set(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    root = tmp_path / "lib"
    root.mkdir()

    code, payload, _ = api.handle("GET", "/webapp/api/roots", headers, b"")
    assert code == 200
    assert payload["roots"] == []

    body = json.dumps({"roots": [str(root)]}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/roots", headers, body)
    assert code == 200
    assert payload["roots"] == [str(root.resolve())]

    code, payload, _ = api.handle("GET", "/webapp/api/roots", headers, b"")
    assert payload["roots"] == [str(root.resolve())]
    assert json.loads(db.get_setting("watch_roots")) == [str(root.resolve())]


def test_api_roots_reject_missing(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    body = json.dumps({"roots": [str(tmp_path / "nope")]}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/roots", headers, body)
    assert code == 400


def test_api_browse_lists_dirs(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    base = tmp_path / "browse"
    (base / "alpha").mkdir(parents=True)
    (base / "beta").mkdir()
    (base / "file.txt").write_text("x")

    code, payload, _ = api.handle(
        "GET", f"/webapp/api/browse?path={base}", headers, b""
    )
    assert code == 200
    names = sorted(d["name"] for d in payload["dirs"])
    assert names == ["alpha", "beta"]
    assert payload["path"] == str(base)
    assert payload["parent"] == str(base.parent)


def test_api_scan_registers(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    root = tmp_path / "vm"
    series = root / "S1"
    (series / "vertical").mkdir(parents=True)
    (series / "vertical" / "final_9x16.mp4").write_bytes(b"x")

    api.handle(
        "POST", "/webapp/api/roots", headers,
        json.dumps({"roots": [str(root)]}).encode(),
    )
    payload = {}
    total = 0
    for _ in range(3):
        code, payload, _ = api.handle("POST", "/webapp/api/scan", headers, b"{}")
        total += payload["stats"]["long"]
    assert code == 200
    assert total == 1
    assert db.fetchone("SELECT id FROM long_videos")


def test_path_key_serves_app(env):
    api, db, clock, cfg, watcher = env
    code, body, ctype = api.handle("GET", "/webapp/k/abc123/", {}, b"")
    assert code == 200
    assert b"Orchestrator" in body
    code, body, _ = api.handle("GET", "/webapp/k/abc123", {}, b"")
    assert code == 200
    assert b"Orchestrator" in body


def test_composed_index_inlines_assets_and_key(env):
    api, db, clock, cfg, watcher = env
    os.environ["WEBAPP_ACCESS_KEY"] = "s3cret"
    try:
        code, body, ctype = api.handle("GET", f"/webapp/k/s3cret/b/{WEBAPP_BUILD}/", {}, b"")
        assert code == 200
        assert ctype.startswith("text/html")
        assert b'src="app.js' not in body
        assert b"__WEBAPP_KEY__" in body
        assert b'"s3cret"' in body
        assert b"gate-msg" in body
        code, body, _ = api.handle("GET", f"/webapp/b/{WEBAPP_BUILD}/", {}, b"")
        assert b'__WEBAPP_KEY__=""' in body
    finally:
        os.environ.pop("WEBAPP_ACCESS_KEY", None)


def test_build_path_serves_app_and_assets(env):
    api, db, clock, cfg, watcher = env
    code, body, _ = api.handle("GET", f"/webapp/b/{WEBAPP_BUILD}/", {}, b"")
    assert code == 200
    assert b"Orchestrator" in body
    code, body, ctype = api.handle("GET", f"/webapp/b/{WEBAPP_BUILD}/app.js", {}, b"")
    assert code == 200
    assert ctype.startswith("application/javascript")


def test_browse_restricted_to_configured_root(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    (tmp_path / "net" / "sub").mkdir(parents=True)
    code, payload, _ = api.handle("GET", "/webapp/api/browse", headers, b"")
    assert code == 200
    assert payload["path"] == str(tmp_path.resolve())
    assert payload["parent"] is None
    # cannot escape the configured root
    code, payload, _ = api.handle(
        "GET", f"/webapp/api/browse?path={tmp_path.parent}", headers, b""
    )
    assert payload["path"] == str(tmp_path.resolve())
    # roots outside the configured root are rejected
    code, _, _ = api.handle(
        "POST", "/webapp/api/roots", headers,
        json.dumps({"roots": [str(tmp_path.parent)]}).encode(),
    )
    assert code == 400


def test_browse_multiple_roots(env, tmp_path, monkeypatch):
    api, db, clock, cfg, watcher = env
    second = tmp_path / "second"
    second.mkdir()
    monkeypatch.setenv("WEBAPP_BROWSE_ROOT", f"{tmp_path},{second}")
    headers = {"X-Telegram-Init-Data": "dev"}
    code, payload, _ = api.handle("GET", "/webapp/api/browse", headers, b"")
    assert code == 200
    assert len(payload["roots"]) == 2
    code, payload, _ = api.handle(
        "GET", f"/webapp/api/browse?root={second}", headers, b""
    )
    assert payload["path"] == str(second.resolve())


def test_metrics_has_live_counts(env):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) VALUES ('v','/m','t',?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
        "VALUES ('long_video', ?, 'youtube', 'scheduled')",
        (vid,),
    )
    code, payload, _ = api.handle("GET", "/webapp/api/metrics", headers, b"")
    assert code == 200
    assert payload["live"]["queue"] == 1


def test_calendar_includes_postiz_posts(env):
    api, db, clock, cfg, watcher = env
    from orchestrator.postiz import PostizPost
    postiz = api.comps["postiz"]
    postiz.posts["pz1"] = PostizPost(
        id="pz1", platform="telegram", scheduled_for=clock.now(),
        status="scheduled", content={"text": "hello from postiz"},
    )
    headers = {"X-Telegram-Init-Data": "dev"}
    code, payload, _ = api.handle("GET", "/webapp/api/calendar", headers, b"")
    assert code == 200
    assert payload["total"] >= 1
    titles = [it["title"] for d in payload["days"] for it in d["items"]]
    assert any("hello from postiz" in x for x in titles)


def test_diag_endpoint(env):
    api, db, clock, cfg, watcher = env
    code, _, _ = api.handle("GET", "/webapp/diag?u=https://x/webapp/&tg=1&k=0", {}, b"")
    assert code == 204


def test_access_key_auth(env):
    api, db, clock, cfg, watcher = env
    os.environ.pop("WEBAPP_DEV", None)
    os.environ["WEBAPP_ACCESS_KEY"] = "s3cret"
    try:
        code, _, _ = api.handle("GET", "/webapp/api/status", {"X-Webapp-Key": "s3cret"}, b"")
        assert code == 200
        code, _, _ = api.handle("GET", "/webapp/api/status", {"X-Webapp-Key": "nope"}, b"")
        assert code == 401
        code, _, _ = api.handle("GET", "/webapp/api/status?key=s3cret", {}, b"")
        assert code == 200
        code, _, _ = api.handle("GET", "/webapp/api/status", {}, b"")
        assert code == 401
    finally:
        os.environ.pop("WEBAPP_ACCESS_KEY", None)
        os.environ["WEBAPP_DEV"] = "1"
