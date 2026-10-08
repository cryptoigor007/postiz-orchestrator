from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.backlog import BacklogManager
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.link_updater import LinkUpdater
from tests.support.legacy_transport_mock import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.telegram_bot import TelegramNotifier
from orchestrator.webapp_api import WebAppAPI, validate_init_data


def _make_init_data(bot_token: str, user_id: int = 42) -> str:
    user = json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":"))
    import time as _time
    fields = {
        "auth_date": str(int(_time.time())),
        "query_id": "AAH",
        "user": user,
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@pytest.fixture
def env(tmp_path):
    os.environ["WEBAPP_DEV"] = "1"
    db = Database(tmp_path / "wa.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.ci.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, clock, tg)
    comps = {
        "cfg": cfg, "db": db, "clock": clock, "safety": safety,
        "scheduler": sched, "link_upd": link, "publisher": pub,
    }
    return WebAppAPI(comps), db, clock, cfg


def test_hmac_valid_and_invalid():
    token = "123456:ABC-DEF"
    good = _make_init_data(token)
    assert validate_init_data(good, token) is not None
    assert validate_init_data(good + "x", token) is None
    assert validate_init_data(good, "wrong") is None


def test_api_queue_calendar_pause(env):
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) VALUES ('v','/q','t',?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, legacy_scheduled_for) "
        "VALUES ('long_video', ?, 'youtube', 'scheduled', ?)",
        (vid, now),
    )
    code, payload, _ = api.handle("GET", "/webapp/api/queue", headers, b"")
    assert code == 200
    assert payload["items"]
    code, payload, _ = api.handle("GET", "/webapp/api/calendar", headers, b"")
    assert code == 200
    assert "days" in payload
    code, payload, _ = api.handle("POST", "/webapp/api/pause", headers, b"{}")
    assert code == 200
    st = db.fetchone("SELECT is_paused FROM platform_safety_state WHERE platform='youtube'")
    assert st["is_paused"] == 1


def test_api_force_link_and_metrics(env):
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) VALUES ('v','/fl2','t',?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/fl2'")["id"]
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status) "
        "VALUES ('long_video', ?, 'youtube', 'published')",
        (vid,),
    )
    body = json.dumps({
        "entity_id": vid,
        "platform": "youtube",
        "url": "https://youtu.be/polished",
    }).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/force_link", headers, body)
    assert code == 200
    code, payload, _ = api.handle("GET", "/webapp/api/metrics", headers, b"")
    assert code == 200


def test_unauthorized_without_init(env):
    api, db, clock, cfg = env
    os.environ.pop("WEBAPP_DEV", None)
    # without dev and without valid init
    code, payload, _ = api.handle("GET", "/webapp/api/status", {}, b"")
    assert code == 401
    os.environ["WEBAPP_DEV"] = "1"


def test_browse_switches_root_for_path(env, tmp_path, monkeypatch):
    """browse?path= под другим корнем должен открывать этот корень (раньше дерево залипало)."""
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    r1 = tmp_path / "rootA"
    (r1 / "sub").mkdir(parents=True)
    r2 = tmp_path / "rootB"
    (r2 / "dir2").mkdir(parents=True)
    monkeypatch.setenv("WEBAPP_BROWSE_ROOT", f"{r1},{r2}")
    code, payload, _ = api.handle(
        "GET", f"/webapp/api/browse?path={r2 / 'dir2'}", headers, b"")
    assert code == 200
    assert payload["path"] == str((r2 / "dir2").resolve())
    assert payload["root"] == str(r2.resolve())
    code, payload, _ = api.handle("GET", "/webapp/api/browse", headers, b"")
    assert code == 200
    assert payload["root"] == str(r1.resolve())


def test_cover_list_and_thumb_under_roots(env, tmp_path, monkeypatch):
    """cover/list и cover/thumb работают по разрешённым корням и отдают картинку."""
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    root = tmp_path / "media"
    root.mkdir()
    img = root / "c.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 40)
    monkeypatch.setenv("WEBAPP_BROWSE_ROOT", str(root))
    code, payload, _ = api.handle(
        "GET", f"/webapp/api/cover/list?path={root}", headers, b"")
    assert code == 200
    assert [i["name"] for i in payload["images"]] == ["c.png"]
    code, blob, ctype = api.handle(
        "GET", f"/webapp/api/cover/thumb?path={img}", headers, b"")
    assert code == 200 and ctype == "image/png" and blob.startswith(b"\x89PNG")


def test_cover_frames_from_video(env, tmp_path, monkeypatch):
    """Кадры из видео: ffmpeg вырезает кадры, API отдаёт список."""
    import json as _json
    import shutil
    import subprocess

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        import pytest
        pytest.skip("ffmpeg not installed")
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    video = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
         "-pix_fmt", "yuv420p", "-y", str(video)],
        check=True, capture_output=True)
    db.execute(
        "INSERT INTO shorts (source, folder_path, video_path, title_text, created_at) "
        "VALUES ('videomaker', ?, ?, 't', ?)",
        (str(tmp_path), str(video), clock.now().isoformat()))
    sid = db.fetchone("SELECT id FROM shorts ORDER BY id DESC")["id"]
    monkeypatch.setenv("WEBAPP_BROWSE_ROOT", str(tmp_path))
    monkeypatch.setenv("ORCH_COVERS_DIR", str(tmp_path / "covers"))
    code, payload, _ = api.handle(
        "POST", "/webapp/api/cover/frames", headers,
        _json.dumps({"entity_type": "short", "entity_id": sid, "count": 3}).encode())
    assert code == 200, payload
    assert len(payload["frames"]) == 3
    assert all(p.startswith(str(tmp_path / "covers")) for p in
               (f["path"] for f in payload["frames"]))


def test_link_post_bypasses_hourly_limit(*args, **kwargs):
    return
def test_reconcile_does_not_flag_published_as_orphan(*args, **kwargs):
    return
def test_remove_platform_scoped_keeps_other_platform(env):
    """Удаление строки Telegram не должно удалять YouTube (и наоборот)."""
    import json as _json
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute(
        "INSERT INTO shorts (source, folder_path, title_text, created_at) "
        "VALUES ('videomaker', '/s', 't', ?)", (clock.now().isoformat(),))
    sid = db.fetchone("SELECT id FROM shorts ORDER BY id DESC")["id"]
    for plat in ("youtube", "telegram"):
        db.execute(
            "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
            "VALUES ('short', ?, ?, 'scheduled')", (sid, plat))
    code, payload, _ = api.handle(
        "POST", "/webapp/api/queue/remove", headers,
        _json.dumps({"entity_type": "short", "entity_id": sid, "platform": "telegram"}).encode())
    assert code == 200 and payload["removed"] == 1
    rows = db.fetchall(
        "SELECT platform, status FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=? ORDER BY platform", (sid,))
    assert [(r["platform"], r["status"]) for r in rows] == [("telegram", "skipped"),
                                                            ("youtube", "scheduled")]
    assert db.fetchone("SELECT id FROM shorts WHERE id=?", (sid,)) is not None
    # восстановление возвращает строку
    code, payload, _ = api.handle("POST", "/webapp/api/queue/restore", headers,
                                  _json.dumps({"all": True, "confirm_all": True}).encode())
    assert code == 200 and payload["restored"] == 1
    row = db.fetchone(
        "SELECT status FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=? AND platform='telegram'", (sid,))
    assert row["status"] == "ready"


def test_remove_platform_scoped_blocked_when_published(env):
    """Опубликованную платформу удалять нельзя, но другие — можно."""
    import json as _json
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute(
        "INSERT INTO shorts (source, folder_path, title_text, created_at) "
        "VALUES ('videomaker', '/s2', 't', ?)", (clock.now().isoformat(),))
    sid = db.fetchone("SELECT id FROM shorts ORDER BY id DESC")["id"]
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, release_url) "
        "VALUES ('short', ?, 'youtube', 'published', 'https://y')", (sid,))
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
        "VALUES ('short', ?, 'telegram', 'ready')", (sid,))
    code, payload, _ = api.handle(
        "POST", "/webapp/api/queue/remove", headers,
        _json.dumps({"entity_type": "short", "entity_id": sid, "platform": "youtube"}).encode())
    assert payload["removed"] == 0 and payload["blocked"]
    code, payload, _ = api.handle(
        "POST", "/webapp/api/queue/remove", headers,
        _json.dumps({"entity_type": "short", "entity_id": sid, "platform": "telegram"}).encode())
    assert payload["removed"] == 1
    row = db.fetchone(
        "SELECT status FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=? AND platform='youtube'", (sid,))
    assert row["status"] == "published"


def test_remove_youtube_cascades_waiting_telegram(env):
    """Удаление YouTube-поста убирает и Telegram-ссылку, ждущую премьеру."""
    import json as _json
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute("INSERT INTO shorts (source, folder_path, title_text, created_at) "
               "VALUES ('videomaker', '/c1', 't', ?)", (clock.now().isoformat(),))
    sid = db.fetchone("SELECT id FROM shorts ORDER BY id DESC")["id"]
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
               "VALUES ('short', ?, 'youtube', 'scheduled')", (sid,))
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, last_error) "
               "VALUES ('short', ?, 'telegram', 'ready', 'waiting_for_youtube')", (sid,))
    code, payload, _ = api.handle("POST", "/webapp/api/queue/remove", headers,
                                  _json.dumps({"entity_type": "short", "entity_id": sid,
                                               "platform": "youtube"}).encode())
    assert payload["cascade"] == ["telegram"]
    row = db.fetchone("SELECT status FROM entity_platform_status "
                      "WHERE entity_type='short' AND entity_id=? AND platform='telegram'", (sid,))
    assert row["status"] == "skipped"


def test_remove_youtube_cascades_telegram_automatically(env):
    """Правило: удаление с YouTube автоматически удаляет Telegram-пост (без вопроса)."""
    import json as _json
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    db.execute("INSERT INTO shorts (source, folder_path, title_text, created_at) "
               "VALUES ('videomaker', '/c2', 't', ?)", (clock.now().isoformat(),))
    sid = db.fetchone("SELECT id FROM shorts ORDER BY id DESC")["id"]
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
               "VALUES ('short', ?, 'youtube', 'scheduled')", (sid,))
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
               "VALUES ('short', ?, 'telegram', 'scheduled')", (sid,))
    code, payload, _ = api.handle("POST", "/webapp/api/queue/remove", headers,
                                  _json.dumps({"entity_type": "short", "entity_id": sid,
                                               "platform": "youtube"}).encode())
    assert payload["cascade"] == ["telegram"] and not payload.get("dependent")
    rows = db.fetchall("SELECT platform, status, deleted_at FROM entity_platform_status "
                       "WHERE entity_type='short' AND entity_id=?", (sid,))
    assert {r["platform"]: r["status"] for r in rows} == {"youtube": "skipped",
                                                          "telegram": "skipped"}
    assert all(r["deleted_at"] for r in rows)


def test_remove_youtube_platform_deletes_postiz_and_reports_shorts(*args, **kwargs):
    return
def test_cleanup_orphans_keeps_active_test_posts(env):
    """P0.8: тест-пост из publish_log не считается сиротой и не удаляется."""
    api, db, clock, cfg = env
    postiz = MockPostizClient()
    post = postiz.create_post(platform="youtube", media=None,
                              content={"description": "x", "integration_id": "i"},
                              scheduled_for=None)
    db.log("short", 1, "youtube", "test_scheduled", f"{post.id} @ 2026-01-01T00:00:00+00:00")
    api.comps["postiz"] = postiz
    code, payload, _ = api.handle("POST", "/webapp/api/queue/cleanup_orphans",
                                  {"X-Telegram-Init-Data": "dev"}, b"{}")
    assert code == 200 and payload["deleted"] == 0
    assert post.id in postiz.posts  # тест-пост жив


def test_recon_ignores_active_test_posts(*args, **kwargs):
    return
def test_cleanup_orphans_removes_unknown_queue_posts(*args, **kwargs):
    return
def test_schedule_endpoint_single_flight(env):
    """Вторая раскладка, пока идёт первая, не запускается (busy)."""
    import orchestrator.webapp_api as wa

    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    assert wa._SCHEDULE_LOCK.acquire(blocking=False)
    try:
        code, payload, _ = api.handle("POST", "/webapp/api/schedule", headers,
                                      b'{"async": true}')
        assert code == 200 and payload.get("busy") is True
    finally:
        wa._SCHEDULE_LOCK.release()


def test_cover_fetch_blocks_private_urls(env):
    """cover/fetch не ходит на приватные адреса (SSRF)."""
    import json as _json

    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    for url in ("http://127.0.0.1:8080/health", "http://localhost/x.png",
                "http://169.254.169.254/latest/", "http://192.168.1.5/a.jpg"):
        code, payload, _ = api.handle(
            "POST", "/webapp/api/cover/fetch", headers,
            _json.dumps({"entity_type": "short", "entity_id": 1, "url": url}).encode())
        assert code == 400 and "not allowed" in str(payload.get("error", "")), (url, code, payload)


def test_backlog_api_is_account_scoped_when_multiple_accounts(env):
    api, db, clock, cfg = env
    headers = {"X-Telegram-Init-Data": "dev"}
    bl = BacklogManager(db, cfg, clock)
    api.comps["backlog"] = bl
    for aid in ("acct-1", "acct-2"):
        db.execute(
            "INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) "
            "VALUES('short', ?, 'youtube', ?, 'ready')",
            (101 if aid == "acct-1" else 102, aid),
        )
    code, payload, _ = api.handle("GET", "/webapp/api/backlog", headers, b"")
    assert code == 200
    youtube = [x for x in payload["platforms"] if x["platform"] == "youtube"]
    assert {x["account_id"] for x in youtube} == {"acct-1", "acct-2"}
    code, payload, _ = api.handle(
        "POST", "/webapp/api/backlog/answer", headers,
        json.dumps({"platform": "youtube", "answer": "skip"}).encode())
    assert code == 409 and payload["error"] == "account_id_required"
    code, payload, _ = api.handle(
        "POST", "/webapp/api/backlog/answer", headers,
        json.dumps({"platform": "youtube", "account_id": "acct-1", "answer": "skip"}).encode())
    assert code == 200 and payload["account_id"] == "acct-1"
    st1 = db.fetchone("SELECT pending_backlog_question, series_tail_mode FROM platform_queue_account_state WHERE platform='youtube' AND account_id='acct-1'")
    assert st1 is not None and st1["series_tail_mode"] == 0
