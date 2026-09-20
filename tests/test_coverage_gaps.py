from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.overflow import move_excess_shorts
from orchestrator.postiz import MockPostizClient
from orchestrator.postiz_factory import create_postiz_client
from orchestrator.postiz_http import HttpPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.watcher import Watcher

ROOT = Path(__file__).resolve().parents[1]


# ---------- postiz_http: полный набор методов ----------

def _http_client(handler):
    return HttpPostizClient(base_url="https://host", token="tok",
                            transport=httpx.MockTransport(handler))


def test_postiz_http_delete_status_release():
    seen = []

    def handler(req):
        seen.append((req.method, req.url.path, req.content.decode() if req.content else ""))
        if req.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"ok": True})

    c = _http_client(handler)
    c.delete_post("p1")
    c.set_status("p1", "draft")
    c.set_release_id("p1", "https://youtu.be/x")
    assert ("DELETE", "/public/v1/posts/p1", "") in seen
    assert ("PUT", "/public/v1/posts/p1/status", '{"status":"draft"}') in seen
    assert ("PUT", "/public/v1/posts/p1/release-id",
            '{"releaseId":"https://youtu.be/x","release_id":"https://youtu.be/x"}') in seen
    c.close()


def test_postiz_http_get_post_404_and_ok():
    def handler404(req):
        return httpx.Response(404, json={"message": "no"})

    c = _http_client(handler404)
    # single-get не поддерживается (404) и список недоступен -> ошибка, НЕ «missing»
    with pytest.raises(httpx.HTTPStatusError):
        c.get_post("missing")
    c.close()

    def handler_list_only(req):
        if req.method == "GET" and req.url.path.endswith("/public/v1/posts"):
            return httpx.Response(200, json={"posts": []})
        return httpx.Response(404, json={})

    c3 = _http_client(handler_list_only)
    assert c3.get_post("missing") is None
    c3.close()

    def handler_ok(req):
        return httpx.Response(200, json={
            "id": "p2", "state": "QUEUE", "publishDate": "2027-01-02T09:00:00.000Z",
            "content": "hi", "integration": {"providerIdentifier": "telegram"},
            "releaseURL": None,
        })

    c2 = _http_client(handler_ok)
    post = c2.get_post("p2")
    assert post is not None and post.status.lower() == "queue"
    c2.close()


def test_postiz_http_list_scheduled_parses_and_filters():
    def handler(req):
        return httpx.Response(200, json={"posts": [
            {"id": "a", "content": "keep", "publishDate": "2027-01-02T09:00:00.000Z",
             "state": "QUEUE", "integration": {"providerIdentifier": "telegram"},
             "releaseURL": None},
            {"id": "b", "content": "skip", "publishDate": "2027-01-03T09:00:00.000Z",
             "state": "ERROR", "integration": {"providerIdentifier": "youtube"}},
        ]})

    c = _http_client(handler)
    rows = c.list_scheduled()
    # ERROR-посты тоже возвращаются: реконсиляция должна видеть их и помечать ошибку
    assert [r.id for r in rows] == ["a", "b"]
    assert rows[0].platform == "telegram"
    assert rows[0].content == {"text": "keep"}
    assert rows[1].status == "error"
    c.close()


def test_postiz_factory_real_and_mock(monkeypatch):
    monkeypatch.setenv("POSTIZ_API_TOKEN", "x")
    assert isinstance(create_postiz_client(dry_run=False), HttpPostizClient)
    monkeypatch.delenv("POSTIZ_API_TOKEN")
    assert isinstance(create_postiz_client(dry_run=False), MockPostizClient)


# ---------- main ----------

def test_main_version_returns_zero(capsys):
    from orchestrator import __version__
    from orchestrator.main import main
    assert main(["--version"]) == 0
    assert __version__ in capsys.readouterr().out


# ---------- scheduler: standalone shorts ----------

def test_schedule_standalone_shorts(tmp_path):
    db = Database(tmp_path / "st.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))  # Monday
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    db.execute(
        "INSERT INTO shorts (source, folder_path, order_index, video_path, title_text, created_at) "
        "VALUES ('shortsmaker','/sm/s0',0,'/sm/s0/v.mp4','S','" + clock.now().isoformat() + "')"
    )
    n = sched.schedule_standalone_shorts(None)
    assert n >= 1
    rows = db.fetchall("SELECT platform, status FROM entity_platform_status WHERE entity_type='short'")
    assert rows and all(r["status"] == "scheduled" for r in rows)


# ---------- watcher: ShortsMaker root ----------

def test_watcher_standalone_root(tmp_path):
    db = Database(tmp_path / "w.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))
    root = tmp_path / "shortsmaker_output"
    (root / "a").mkdir(parents=True)
    (root / "a" / "clip.mp4").write_bytes(b"x")
    w = Watcher(db, cfg, clock, [str(root)])
    total = 0
    for _ in range(3):
        total += w.scan()["standalone"]
    assert total == 1
    assert db.fetchone("SELECT id FROM shorts WHERE source='shortsmaker'")


# ---------- overflow ----------

def test_move_excess_shorts(tmp_path):
    db = Database(tmp_path / "o.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    cfg.limits.max_shorts_per_long_video = 2
    cfg.limits.overflow_move_files = True  # перенос файлов — опционально
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))
    series = tmp_path / "series"
    (series / "shorts").mkdir(parents=True)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) VALUES ('v',?, 't', ?)",
        (str(series), clock.now().isoformat()),
    )
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    for i in range(4):
        d = series / "shorts" / f"short_{i}"
        d.mkdir()
        db.execute(
            "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, created_at) "
            "VALUES ('videomaker', ?, ?, ?, ?)",
            (vid, str(d), i, clock.now().isoformat()),
        )
    moved = move_excess_shorts(db, cfg, clock, vid)
    assert moved == 2
    assert (series / "shorts_overflow").is_dir()
    skipped = db.fetchall("SELECT status FROM entity_platform_status WHERE entity_type='short' AND status='skipped'")
    assert len(skipped) >= 2


# ---------- http_server ----------

def test_http_server_health_and_webapp_404(tmp_path):
    import socket

    from orchestrator.http_server import start_http_server

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    free_port = s.getsockname()[1]
    s.close()
    srv = start_http_server(free_port, lambda: {"ok": True, "n": 1})
    assert srv is not None
    try:
        port = srv.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
            body = json.loads(r.read().decode())
        assert body["ok"] is True
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
        assert e.value.code == 404
    finally:
        srv.shutdown()


def test_tg_transport_no_ack_persistent_watermark():
    from orchestrator.telegram_transport import TelegramTransport

    store = {"v": 0}
    t = TelegramTransport(token="x", load_seen=lambda: store["v"],
                          save_seen=lambda v: store.update(v=v))
    t.no_ack = True
    assert t._accept({"update_id": 100}) is True
    assert store["v"] == 100
    assert t._accept({"update_id": 100}) is False
    # «рестарт» процесса: отметка читается из хранилища, повторно не отвечаем
    t2 = TelegramTransport(token="x", load_seen=lambda: store["v"],
                           save_seen=lambda v: store.update(v=v))
    t2.no_ack = True
    assert t2._accept({"update_id": 100}) is False
    assert t2._accept({"update_id": 101}) is True
    assert store["v"] == 101


def test_tg_bot_ack_and_help(tmp_path):
    from datetime import UTC, datetime
    from pathlib import Path

    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.db import Database
    from orchestrator.telegram_bot import TelegramNotifier, setup_commands

    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db = Database(tmp_path / "tg.sqlite")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    bot = TelegramNotifier(cfg, db, clock)
    class _Comps(dict):
        def __missing__(self, key):
            return None
    setup_commands(bot, _Comps())
    own = cfg.telegram.allowed_chat_ids[0]
    assert "Принято" in bot.handle_update(own, "привет")
    assert "Неизвестная" in bot.handle_update(own, "/nosuchcmd")
    assert "Команды" in bot.handle_update(own, "/help")


def test_tg_bot_queue_with_titles(tmp_path):
    from datetime import UTC, datetime
    from pathlib import Path

    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.db import Database
    from orchestrator.telegram_bot import TelegramNotifier, setup_commands

    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db = Database(tmp_path / "q.sqlite")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    bot = TelegramNotifier(cfg, db, clock)

    class _Comps(dict):
        def __missing__(self, key):
            return None

    comps = _Comps()
    comps["db"] = db
    comps["cfg"] = cfg
    comps["clock"] = clock
    setup_commands(bot, comps)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, created_at) "
        "VALUES ('videomaker', 'f1', 's1', 'Мой фильм', '2026-01-01T00:00:00+00:00')"
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', ?, 'telegram', 'scheduled', "
        "'2026-09-22T12:59:40+00:00')",
        (lv["id"],),
    )
    own = cfg.telegram.allowed_chat_ids[0]
    out = bot.handle_update(own, "/queue")
    assert "Очередь" in out and "Мой фильм" in out
    assert "📅 <b>Вт, 22 сентября</b>" in out   # день визуально выделен
    assert "✈️" in out                            # значок Telegram


def test_hourly_limit_ignores_deleted(tmp_path):
    from datetime import UTC, datetime
    from pathlib import Path

    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.db import Database
    from orchestrator.postiz import MockPostizClient
    from orchestrator.publisher import Publisher
    from orchestrator.safety import SafetyChecker

    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    cfg.limits.postiz_create_per_hour = 3
    db = Database(tmp_path / "h.sqlite")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    now = clock.now().isoformat()
    # 30 "созданий" в логе, но постов в базе нет (удалены)
    for i in range(30):
        db.execute(
            "INSERT INTO publish_log (entity_type, entity_id, platform, action, created_at) "
            "VALUES ('long_video', ?, 'telegram', 'created', ?)",
            (i + 100, now),
        )
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, vertical_path, created_at) "
        "VALUES ('videomaker', '/x', 'X', '/x/v.mp4', ?)",
        (now,),
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    post = pub.publish("long_video", lv["id"], "telegram", "/x/v.mp4", {"title": "T"},
                       datetime(2026, 3, 11, 13, 0, tzinfo=UTC))
    assert post is not None  # удалённые не считаются лимитом


def test_rate_limit_does_not_pause_platform(tmp_path):
    from datetime import UTC, datetime
    from pathlib import Path

    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.db import Database
    from orchestrator.safety import SafetyChecker

    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db = Database(tmp_path / "rl.sqlite")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    safety = SafetyChecker(db, cfg, clock)
    db.ensure_platform_states(["telegram"])
    safety.handle_error("telegram", "Client error '429 Too Many Requests' for url ...")
    assert safety.is_platform_paused("telegram") is False
    safety.handle_error("telegram", "401 Unauthorized: token expired")
    assert safety.is_platform_paused("telegram") is True


def test_jobs_progress_and_cancel():
    import time

    from orchestrator.jobs import JobRegistry

    reg = JobRegistry()
    job = reg.start("schedule", "Планирование", total=4)
    job.tick(1)
    job.tick(1)
    snap = reg.snapshot()
    assert snap["percent"] == 50 and snap["done"] == 2
    assert snap["eta"] is not None
    assert reg.cancel() is True
    assert job.cancelled
    job.finish("done", "ok")
    assert snap is not None
    snap2 = reg.snapshot()
    assert snap2["status"] == "cancelled"
    # после завершения и паузы (>60с) snapshot скрывается
    job.state.finished_at = time.time() - 120
    assert reg.snapshot() is None


def test_tg_split_long_text():
    from orchestrator.telegram_transport import split_text

    text = "\n".join(f"строка номер {i} с некоторым текстом" for i in range(300))
    parts = split_text(text, 500)
    assert len(parts) > 1
    assert all(len(p) <= 500 for p in parts)
    assert "\n".join(parts) == text


def test_tg_queue_no_truncation(tmp_path):
    from datetime import UTC, datetime
    from pathlib import Path

    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.db import Database
    from orchestrator.telegram_bot import TelegramNotifier, setup_commands

    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db = Database(tmp_path / "long.sqlite")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    bot = TelegramNotifier(cfg, db, clock)

    class _Comps(dict):
        def __missing__(self, key):
            return None

    comps = _Comps()
    comps["db"] = db
    comps["cfg"] = cfg
    comps["clock"] = clock
    setup_commands(bot, comps)
    long_title = "Очень длинное название фильма, которое раньше обрезалось многоточием в очереди"
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, created_at) "
        "VALUES ('videomaker', '/lt', 'lt', ?, '2026-01-01T00:00:00+00:00')",
        (long_title,),
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', ?, 'youtube', 'scheduled', "
        "'2026-09-22T13:00:00+00:00')",
        (lv["id"],),
    )
    out = bot.handle_update(cfg.telegram.allowed_chat_ids[0], "/queue")
    assert long_title in out
    assert "…" not in out
