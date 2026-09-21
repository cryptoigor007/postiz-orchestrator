from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.metrics import Metrics
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.telegram_transport import TelegramTransport


def test_multi_platform_schedule(tmp_path):
    db = Database(tmp_path / "m.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    cfg.platforms["telegram"].post_mode = "media"  # тест мультиплатформы
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, vertical_path, "
        "title_text, description_text, created_at) VALUES "
        "('videomaker', '/mp', 'M', '/mp/w.mp4', '/mp/v.mp4', 'T', 'D', ?)",
        (clock.now().isoformat(),),
    )
    n = sched.schedule_long_videos()
    assert n >= 2  # at least youtube + facebook (wide) or vertical platforms
    platforms = {
        r["platform"]
        for r in db.fetchall(
            "SELECT platform FROM entity_platform_status WHERE entity_type='long_video'"
        )
    }
    assert "youtube" in platforms
    assert len(platforms) >= 2


def test_orphan_on_create_fail(tmp_path):
    db = Database(tmp_path / "o.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    db.ensure_platform_states(["youtube"])
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    postiz.fail_create = True
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', '/or', 't', '/or/w.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos")["id"]
    try:
        pub.publish(
            "long_video", vid, "youtube", "/or/w.mp4", {"title": "x"},
            datetime(2026, 3, 11, 13, 0, tzinfo=UTC),
        )
    except Exception:
        pass
    assert len(postiz.orphan_media_ids()) >= 1
    cleared = postiz.clear_orphan_media()
    assert cleared
    assert postiz.orphan_media_ids() == []


def test_metrics_and_health():
    m = Metrics(path=None)
    m.incr("scheduled_long", 2)
    m.tick_cycle()
    assert m.snapshot()["scheduled_long"] == 2
    assert m.snapshot()["cycles"] == 1


def test_tg_queue_push():
    seen = []

    def handler(chat_id, text):
        seen.append((chat_id, text))
        return None

    tr = TelegramTransport(token="", on_message=handler)
    tr.mode = "off"
    tr._stop = False
    import threading
    w = threading.Thread(target=tr._worker, daemon=True)
    w.start()
    tr.push_update(1, "/status")
    tr._q.put(None)  # stop worker promptly
    w.join(timeout=2)
    assert seen and seen[0][1] == "/status"


def test_stage_config_loads():
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.stage.yaml")
    assert cfg.platforms["telegram"].enabled is True
    assert cfg.platforms["youtube"].enabled is False


def test_content_length_cap_rejects_big_body(monkeypatch):
    """P0.7: Content-Length > капа → 413 без чтения тела."""
    import socket as _sk

    from orchestrator.http_server import start_http_server

    monkeypatch.setenv("ORCH_MAX_BODY_BYTES", "1024")
    _s = _sk.socket()
    _s.bind(("127.0.0.1", 0))
    free_port = _s.getsockname()[1]
    _s.close()
    srv = start_http_server(free_port, lambda: {"ok": True},
                            lambda m, p, h, b: (200, {"ok": True}, "application/json"))
    assert srv is not None
    port = srv.server_address[1]
    try:
        import http.client as _hc

        # маленькое тело — ок
        c = _hc.HTTPConnection("127.0.0.1", port, timeout=5)
        c.request("POST", "/webapp/api/x", body=b"{}", headers={"Content-Length": "2"})
        assert c.getresponse().status in (200, 404)
        c.close()
        # большое — 413 до чтения
        c = _hc.HTTPConnection("127.0.0.1", port, timeout=5)
        c.putrequest("POST", "/webapp/api/x")
        c.putheader("Content-Length", "999999")
        c.endheaders()
        r = c.getresponse()
        assert r.status == 413
        c.close()
    finally:
        srv.shutdown()


def test_metrics_survive_restart(tmp_path):
    """Счётчики метрик не теряются при рестарте (читаем прошлый файл)."""
    from orchestrator.metrics import Metrics

    path = tmp_path / "metrics.json"
    m1 = Metrics(path)
    m1.incr("cycles", 3)
    m1.incr("test_cancelled", 2)
    m1.flush()
    m2 = Metrics(path)
    assert m2.data["cycles"] == 3
    assert m2.data["test_cancelled"] == 2
    m2.incr("cycles", 1)
    m2.flush()
    m3 = Metrics(path)
    assert m3.data["cycles"] == 4 and m3.data["test_cancelled"] == 2
