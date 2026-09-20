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
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.link_updater import LinkUpdater
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.telegram_bot import TelegramNotifier
from orchestrator.webapp_api import WebAppAPI, validate_init_data


def _make_init_data(bot_token: str, user_id: int = 42) -> str:
    user = json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":"))
    fields = {
        "auth_date": "1700000000",
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
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    tg = TelegramNotifier(cfg, db, clock)
    link = LinkUpdater(db, cfg, postiz, clock, tg)
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
        "(entity_type, entity_id, platform, status, postiz_scheduled_for) "
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


def test_link_post_bypasses_hourly_limit(env, tmp_path):
    """Пост-ссылка (priority=link) не блокируется hourly_create_per_hour."""
    from orchestrator.publisher import Publisher
    api, db, clock, cfg = env
    cfg.limits.postiz_create_per_hour = 1
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) "
        "VALUES ('v', '/lv', 't', ?)", (clock.now().isoformat(),))
    lv = db.fetchone("SELECT id FROM long_videos")["id"]
    db.log("long_video", lv, "telegram", "created", "x")
    pub = Publisher(db, cfg, api.comps.get("postiz") or __import__(
        "orchestrator.postiz", fromlist=["MockPostizClient"]).MockPostizClient(),
        api.comps["safety"], clock, dry_run=False)
    post = pub.publish("long_video", lv, "telegram", None,
                       {"title": "", "description": "ссылка", "hashtags": "",
                        "priority": "link"}, clock.now())
    assert post is not None


def test_reconcile_does_not_flag_published_as_orphan(env):
    """Опубликованные посты (published) не должны считаться «лишними» при сверке."""
    from orchestrator.status_sync import Reconciliation

    api, db, clock, cfg = env
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) "
        "VALUES ('v', '/lv', 't', ?)", (now,))
    lv = db.fetchone("SELECT id FROM long_videos ORDER BY id DESC")["id"]
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, "
        "status, postiz_post_id, release_url, published_at) "
        "VALUES ('long_video', ?, 'youtube', 'published', 'pub1', 'https://y', ?)",
        (lv, now))
    postiz = api.comps.get("postiz")
    if postiz is None:
        from orchestrator.postiz import MockPostizClient, PostizPost
        postiz = MockPostizClient()
        postiz.posts["pub1"] = PostizPost(id="pub1", platform="youtube",
                                          scheduled_for=None, status="published",
                                          content={"text": "x"})
    recon = Reconciliation(db, postiz, clock)
    res = recon.run()
    assert res["orphans"] == 0
