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
    assert payload["items"] == [{"path": str(root.resolve()), "kind": "auto"}]

    code, payload, _ = api.handle("GET", "/webapp/api/roots", headers, b"")
    assert payload["roots"] == [str(root.resolve())]
    assert payload["items"] == [{"path": str(root.resolve()), "kind": "auto"}]
    assert json.loads(db.get_setting("watch_roots")) == [
        {"path": str(root.resolve()), "kind": "auto"}
    ]

    # тип корня
    body = json.dumps({"items": [{"path": str(root), "kind": "shorts"}]}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/roots", headers, body)
    assert code == 200
    assert payload["items"] == [{"path": str(root.resolve()), "kind": "shorts"}]
    body = json.dumps({"items": [{"path": str(root), "kind": "wat"}]}).encode()
    code, _, _ = api.handle("POST", "/webapp/api/roots", headers, body)
    assert code == 400


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
    assert payload["checked"] >= 1          # сколько папок реально проверено
    assert payload["at"]                    # время скана
    assert "missing" in payload and "unstable" in payload
    assert db.fetchone("SELECT id FROM long_videos")


def test_path_key_serves_app(env, monkeypatch):
    monkeypatch.setenv("ORCH_LEGACY_PATH_KEY", "1")
    api, db, clock, cfg, watcher = env
    code, body, ctype = api.handle("GET", "/webapp/k/abc123/", {}, b"")
    assert code == 200
    assert b"Orchestrator" in body
    code, body, _ = api.handle("GET", "/webapp/k/abc123", {}, b"")
    assert code == 200
    assert b"Orchestrator" in body


def test_path_key_denied_without_legacy(env, monkeypatch):
    monkeypatch.delenv("ORCH_LEGACY_PATH_KEY", raising=False)
    monkeypatch.setenv("ORCH_LEGACY_PATH_KEY", "0")
    api, db, clock, cfg, watcher = env
    code, body, _ = api.handle("GET", "/webapp/k/abc123/", {}, b"")
    assert code == 404


def test_composed_index_inlines_assets_and_key(env, monkeypatch):
    monkeypatch.setenv("ORCH_LEGACY_PATH_KEY", "1")
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


def test_build_path_rejects_absolute_and_dotdot(env, tmp_path):
    """P0 (8.4.5): /webapp/b/<build>//abs/path уходил за WEBAPP_DIR (Path / abs == abs)."""
    api, db, clock, cfg, watcher = env
    secret = tmp_path / "secret.env"
    secret.write_text("TOPSECRET=1", encoding="utf-8")
    # абсолютный путь из URL (без ключа) — файл существует, но вне webapp/
    code, body, _ = api.handle(
        "GET", f"/webapp/b/{WEBAPP_BUILD}//{str(secret).lstrip('/')}", {}, b""
    )
    assert code == 404, (code, body[:80])
    # обычный ..-обход по-прежнему отбивается
    code, _, _ = api.handle("GET", f"/webapp/b/{WEBAPP_BUILD}/../../etc/host.conf", {}, b"")
    assert code == 404
    # легитимный ассет по-прежнему отдаётся
    code, _, _ = api.handle("GET", f"/webapp/b/{WEBAPP_BUILD}/styles.css", {}, b"")
    assert code == 200


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


def test_api_schedule_settings_and_groups(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}

    code, payload, _ = api.handle("GET", "/webapp/api/schedule_settings", headers, b"")
    assert code == 200
    assert payload["platforms"]
    eff = payload["effective"]["telegram"]
    assert eff["long"]["time"] == "16:00"
    assert eff["thematic"]["time"] == "20:30"

    # сохранить override платформы
    body = json.dumps({"settings": {"telegram": {
        "long": {"days": ["sun"], "time": "11:00"},
        "thematic": {"time": "19:30"},
        "standalone": {"days": ["mon"], "times": ["10:00"]},
        "daily_limit": 4,
    }}}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/schedule_settings", headers, body)
    assert code == 200
    code, payload, _ = api.handle("GET", "/webapp/api/schedule_settings", headers, b"")
    eff = payload["effective"]["telegram"]
    assert eff["long"]["time"] == "11:00"
    assert eff["daily_limit"] == 4

    # невалидное время
    body = json.dumps({"settings": {"telegram": {"long": {"time": "99:99"}}}}).encode()
    code, _, _ = api.handle("POST", "/webapp/api/schedule_settings", headers, body)
    assert code == 400
    # неизвестная платформа
    body = json.dumps({"settings": {"myspace": {"long": {"time": "10:00"}}}}).encode()
    code, _, _ = api.handle("POST", "/webapp/api/schedule_settings", headers, body)
    assert code == 400

    # группы
    body = json.dumps({"groups": [{"name": "Основные", "platforms": ["telegram", "youtube"]}]}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/groups", headers, body)
    assert code == 200
    code, payload, _ = api.handle("GET", "/webapp/api/schedule_settings", headers, b"")
    assert payload["groups"][0]["name"] == "Основные"
    body = json.dumps({"groups": [{"name": "X", "platforms": ["nosuch"]}]}).encode()
    code, _, _ = api.handle("POST", "/webapp/api/groups", headers, body)
    assert code == 400
    # настройки для группы
    body = json.dumps({"settings": {"group:Основные": {"long": {"time": "18:00"}}}}).encode()
    code, _, _ = api.handle("POST", "/webapp/api/schedule_settings", headers, body)
    assert code == 200
    code, payload, _ = api.handle("GET", "/webapp/api/schedule_settings", headers, b"")
    assert payload["effective"]["youtube"]["long"]["time"] == "18:00"


def test_api_calendar_titles_and_local_time(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, created_at) "
        "VALUES ('videomaker', ?, ?, ?, ?)",
        (str(tmp_path / "series"), "s1", "Мой фильм", "2026-01-01T00:00:00+00:00"),
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for, postiz_post_id) VALUES ('long_video', ?, 'telegram', "
        "'scheduled', '2026-09-22T12:59:40+00:00', 'pid1')",
        (lv["id"],),
    )
    code, payload, _ = api.handle("GET", "/webapp/api/calendar", headers, b"")
    assert code == 200
    items = payload["days"][0]["items"]
    assert items[0]["title"] == "Фильм: Мой фильм"
    assert items[0]["time"] == "15:59"  # UTC -> Europe/Moscow
    assert items[0]["date"] == "2026-09-22"


def test_api_schedule_start_date_validation(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    body = json.dumps({"start_date": "22-09-2026"}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/schedule", headers, body)
    assert code == 400
    body = json.dumps({"start_date": "2026-09-25"}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/schedule", headers, body)
    assert code == 200 and payload["start_date"] == "2026-09-25"


def test_api_queue_remove(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) "
        "VALUES ('videomaker', '/s1', 'S1', '2026-01-01T00:00:00+00:00')"
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for, postiz_post_id) VALUES ('long_video', ?, 'telegram', "
        "'scheduled', '2026-09-22T13:00:00+00:00', 'p1')",
        (lv["id"],),
    )
    body = json.dumps({"entity_type": "long_video", "entity_id": lv["id"]}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/queue/remove", headers, body)
    assert code == 200 and payload["removed"] == 1
    row = db.fetchone("SELECT status, deleted_at FROM entity_platform_status")
    assert row["status"] == "skipped" and row["deleted_at"]
    # мягкое удаление: сущность остаётся (корзина), скан её не вернёт
    assert db.fetchone("SELECT * FROM long_videos") is not None


def test_api_queue_remove_cascade_to_shorts(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) "
        "VALUES ('videomaker', '/s1', 'S1', '2026-01-01T00:00:00+00:00')"
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    db.execute(
        "INSERT INTO shorts (source, parent_video_id, folder_path, video_path, created_at) "
        "VALUES ('videomaker', ?, '/s1/shorts/short_001', '/s1/shorts/s1.mp4', "
        "'2026-01-01T00:00:00+00:00')",
        (lv["id"],),
    )
    sh = db.fetchone("SELECT id FROM shorts")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for, postiz_post_id) VALUES ('long_video', ?, 'telegram', "
        "'scheduled', '2026-09-22T13:00:00+00:00', 'p-long')",
        (lv["id"],),
    )
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for, postiz_post_id) VALUES ('short', ?, 'telegram', "
        "'scheduled', '2026-09-22T17:30:00+00:00', 'p-short')",
        (sh["id"],),
    )
    body = json.dumps({"entity_type": "long_video", "entity_id": lv["id"]}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/queue/remove", headers, body)
    assert code == 200
    assert payload["removed"] == 2  # фильм + его шортс
    rows = db.fetchall("SELECT status FROM entity_platform_status")
    assert rows and all(r["status"] == "skipped" for r in rows)
    # мягкое удаление: обе сущности остаются в базе (корзина)
    assert db.fetchone("SELECT * FROM long_videos") is not None
    assert db.fetchone("SELECT * FROM shorts") is not None


def test_api_queue_remove_published_blocked(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for, postiz_post_id) VALUES ('long_video', 1, 'telegram', "
        "'scheduled', '2026-09-22T13:00:00+00:00', 'p-tg')"
    )
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for, postiz_post_id) VALUES ('long_video', 1, 'youtube', "
        "'scheduled', '2026-09-22T13:00:00+00:00', 'p-yt')"
    )
    db.execute(
        "UPDATE entity_platform_status SET status='published' WHERE platform='telegram'"
    )
    body = json.dumps({"entity_type": "long_video", "entity_id": 1}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/queue/remove", headers, body)
    assert code == 200 and payload["removed"] == 0 and payload["blocked"]
    assert db.fetchone("SELECT COUNT(*) AS c FROM entity_platform_status")["c"] == 2


def test_api_queue_restore(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_post_id, last_error) VALUES ('long_video', 1, 'telegram', 'skipped', "
        "'p1', 'removed_by_user')"
    )
    code, payload, _ = api.handle("POST", "/webapp/api/queue/restore", headers,
                                  json.dumps({"all": True}).encode())
    assert code == 200 and payload["restored"] == 1
    row = db.fetchone("SELECT status, postiz_post_id, last_error FROM entity_platform_status")
    assert row["status"] == "ready" and row["postiz_post_id"] is None and row["last_error"] is None


def test_api_queue_cover_candidates(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    d = tmp_path / "series" / "shorts" / "short_001"
    d.mkdir(parents=True)
    video = d / "short_001.mp4"
    video.write_bytes(b"v" * 100)
    (d / "short_001_cover.jpg").write_bytes(b"jpg")
    covdir = tmp_path / "series" / "обложки"
    covdir.mkdir()
    (covdir / "alt.jpg").write_bytes(b"jpg")
    db.execute(
        "INSERT INTO shorts (source, folder_path, video_path, created_at) "
        "VALUES ('shortsmaker', ?, ?, '2026-01-01T00:00:00+00:00')",
        (str(d), str(video)),
    )
    sh = db.fetchone("SELECT id FROM shorts")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('short', ?, 'youtube', 'scheduled', "
        "'2026-09-22T17:30:00+00:00')",
        (sh["id"],),
    )
    code, payload, _ = api.handle("GET", "/webapp/api/queue", headers, b"")
    item = payload["items"][0]
    assert item["covers"]
    assert any(c.endswith("short_001_cover.jpg") for c in item["covers"])
    # сохранение обложки через редактор
    body = json.dumps({"entity_type": "short", "entity_id": sh["id"], "platform": "youtube",
                       "title": "T", "description": "D", "hashtags": "#t",
                       "cover": str(d / "short_001_cover.jpg")}).encode()
    code, _, _ = api.handle("POST", "/webapp/api/queue/edit", headers, body)
    assert code == 200
    row = db.fetchone("SELECT cover_path FROM shorts")
    assert row["cover_path"].endswith("short_001_cover.jpg")


def test_api_queue_has_tg_flag(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', 1, 'youtube', 'scheduled', "
        "'2026-09-22T13:00:00+00:00')"
    )
    code, payload, _ = api.handle("GET", "/webapp/api/queue", headers, b"")
    assert payload["items"][0]["has_tg"] is False
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', 1, 'telegram', 'scheduled', "
        "'2026-09-22T13:15:00+00:00')"
    )
    code, payload, _ = api.handle("GET", "/webapp/api/queue", headers, b"")
    assert all(i["has_tg"] is True for i in payload["items"])


def test_compose_keeps_backslash_n(env):
    api, db, clock, cfg, watcher = env
    code, body, _ = api.handle("GET", "/webapp/b/54/", {}, b"")
    if code != 200:
        code, body, _ = api.handle("GET", f"/webapp/b/{__import__('orchestrator.webapp_api', fromlist=['WEBAPP_BUILD']).WEBAPP_BUILD}/", {}, b"")
    assert code == 200
    assert b'"\\n\\n"' in body  # escape-последовательности не превратились в реальные переводы строк


def test_api_queue_remove_film_only_keeps_shorts(env, tmp_path):
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) "
        "VALUES ('videomaker', '/fo', 'FO', '2026-01-01T00:00:00+00:00')"
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    db.execute(
        "INSERT INTO shorts (source, parent_video_id, folder_path, video_path, created_at) "
        "VALUES ('videomaker', ?, '/fo/shorts/s1', '/fo/shorts/s1/a.mp4', "
        "'2026-01-01T00:00:00+00:00')",
        (lv["id"],),
    )
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_post_id, postiz_scheduled_for) VALUES ('long_video', ?, 'youtube', "
        "'scheduled', 'p1', '2026-10-20T13:00:00+00:00')",
        (lv["id"],),
    )
    body = json.dumps({"entity_type": "long_video", "entity_id": lv["id"],
                       "with_shorts": False}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/queue/remove", headers, body)
    assert code == 200 and payload["removed"] == 1
    # «только серия»: фильм в корзине, шортс остаётся привязанным и не тронут
    film = db.fetchone("SELECT status FROM entity_platform_status "
                       "WHERE entity_type='long_video' AND entity_id=?", (lv["id"],))
    assert film["status"] == "skipped"
    sh = db.fetchone("SELECT parent_video_id FROM shorts")
    assert sh is not None and sh["parent_video_id"] == lv["id"]


def test_queue_restore_invalid_id_does_not_restore_all(env):
    """P2-4: невалидный entity_id не должен восстанавливать ВСЕ skipped."""
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    for eid in (1, 2):
        db.execute(
            "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
            "VALUES ('short', ?, 'youtube', 'skipped')",
            (eid,),
        )
    code, payload, _ = api.handle(
        "POST", "/webapp/api/queue/restore", headers,
        json.dumps({"entity_type": "short", "entity_id": 0}).encode(),
    )
    assert code == 400
    left = db.fetchall("SELECT entity_id FROM entity_platform_status WHERE status='skipped'")
    assert len(left) == 2


def test_rate_limit_ignores_spoofed_key_header(env, monkeypatch):
    """P2-1: произвольный X-Webapp-Key не должен создавать новый bucket (обход лимита)."""
    api, db, clock, cfg, watcher = env
    monkeypatch.setenv("WEBAPP_RATE_LIMIT", "1")
    api._rl.clear()
    auth = {"user": {"id": 999}}
    assert api._rate_limited({"X-Webapp-Key": "spoof-1"}, auth) is False
    assert api._rate_limited({"X-Webapp-Key": "spoof-2"}, auth) is True


def test_calendar_survives_postiz_post_without_text(env):
    """P2-2: пост Postiz без текста не должен обрывать весь блок Postiz в календаре."""
    api, db, clock, cfg, watcher = env
    headers = {"X-Telegram-Init-Data": "dev"}
    postiz = api.comps["postiz"]
    postiz.create_post("youtube", None, {"description": "no text key"},
                       datetime(2026, 3, 11, 16, 0, tzinfo=UTC))
    postiz.create_post("youtube", None, {"text": "GOOD POST"},
                       datetime(2026, 3, 12, 16, 0, tzinfo=UTC))
    code, payload, _ = api.handle("GET", "/webapp/api/calendar", headers, b"")
    assert code == 200
    titles = [i.get("title", "") for day in payload.get("days", [])
              for i in day.get("items", [])]
    assert any("GOOD POST" in t for t in titles), titles
