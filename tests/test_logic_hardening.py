from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.postiz import MockPostizClient, PostizPost
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.telegram_transport import TelegramTransport

ROOT = Path(__file__).resolve().parents[1]


def env(tmp_path, now=None):
    db = Database(tmp_path / "h.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    db.ensure_platform_states(list(cfg.platforms.keys()))
    clock = FakeClock(now or datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    return db, cfg, clock, postiz, safety, pub, sched


def _long(db, clock, folder="/s"):
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('v', ?, 'T', ?, ?)", (folder, folder + "/w.mp4", clock.now().isoformat()))
    return db.fetchone("SELECT id FROM long_videos WHERE folder_path=?", (folder,))["id"]


def test_scheduler_survives_publish_failure(tmp_path, monkeypatch):
    db, cfg, clock, postiz, safety, pub, sched = env(tmp_path)
    _long(db, clock, "/a")
    _long(db, clock, "/b")
    calls = {"n": 0}
    real = pub.publish

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real(*a, **kw)

    monkeypatch.setattr(pub, "publish", flaky)
    n = sched.schedule_long_videos()   # не должно бросить исключение
    assert n >= 1                      # второе видео всё равно запланировано
    rows = db.fetchall("SELECT entity_id FROM entity_platform_status WHERE entity_type='long_video'")
    assert rows


def test_link_update_rolls_back_on_failed_recreate(tmp_path, monkeypatch):
    from orchestrator.link_updater import LinkUpdater
    from orchestrator.telegram_bot import TelegramNotifier
    db, cfg, clock, postiz, safety, pub, sched = env(tmp_path)
    tg = TelegramNotifier(cfg, db, clock)
    upd = LinkUpdater(db, cfg, postiz, clock, tg)
    vid = _long(db, clock, "/s2")
    t = datetime(2026, 3, 10, 16, 0, tzinfo=UTC).isoformat()
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_post_id, postiz_scheduled_for, published_at, release_url) "
        "VALUES ('long_video', ?, 'youtube', 'published', 'p1', ?, ?, 'https://youtu.be/x')",
        (vid, t, t))
    db.execute(
        "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, video_path, "
        "title_text, description_text, created_at) VALUES ('videomaker', ?, '/s2/sh0', 0, "
        "'/s2/sh0/v.mp4', 'S', 'D', ?)", (vid, clock.now().isoformat()))
    sid = db.fetchone("SELECT id FROM shorts")["id"]
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_post_id, postiz_scheduled_for) VALUES ('short', ?, 'youtube', 'scheduled', "
        "'old1', ?)", (sid, t))
    postiz.posts["old1"] = PostizPost(id="old1", platform="youtube",
                                      scheduled_for=datetime(2026, 3, 10, 16, 0, tzinfo=UTC),
                                      status="scheduled")

    monkeypatch.setattr(sched.publisher, "publish", lambda *a, **kw: None)  # публикация не удалась
    n = upd.refresh_thematic_after_url(vid, "youtube", sched)
    assert n == 0
    row = db.fetchone(
        "SELECT postiz_post_id, status FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=?", (sid,))
    assert row["postiz_post_id"] == "old1"   # старая привязка восстановлена
    assert row["status"] == "scheduled"
    assert "old1" in postiz.posts            # старый пост не удалён


def test_backlog_missed_window_auto_distributes(tmp_path):
    from orchestrator.backlog import BacklogManager
    db, cfg, clock, postiz, safety, pub, sched = env(tmp_path, now=datetime(2026, 3, 10, 15, 0, tzinfo=UTC))
    vid = _long(db, clock, "/S1")
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
               "release_url) VALUES ('long_video', ?, 'youtube', 'published', 'u')", (vid,))
    for i in range(2):
        db.execute("INSERT INTO shorts (source, parent_video_id, folder_path, order_index, "
                   "video_path, title_text, created_at) VALUES ('videomaker', ?, ?, ?, ?, 'S', ?)",
                   (vid, f"/S1/s{i}", i, f"/S1/s{i}/v.mp4", clock.now().isoformat()))
    mgr = BacklogManager(db, cfg, clock, scheduler=sched)
    # окно вопроса пропущено (оркестратор лежал): сейчас уже после слота 16:00 MSK
    clock.set(datetime(2026, 3, 10, 13, 30, tzinfo=UTC))  # 16:30 MSK
    n = mgr.missed_default("youtube", clock.now())
    assert n == 2
    assert mgr.missed_default("youtube", clock.now()) == 0  # повторно не срабатывает


def test_transport_offset_window():
    tr = TelegramTransport(token="x", on_message=lambda c, t: None)
    tr.no_ack = True
    tr._last_update_id = 100
    assert tr._next_offset() == 50      # держим последние 50 неподтверждёнными
    tr._last_update_id = 10
    assert tr._next_offset() == 0
    tr.no_ack = False
    tr._offset = 777
    assert tr._next_offset() == 777


def test_jitter_never_schedules_in_past(tmp_path):
    db, cfg, clock, postiz, safety, pub, sched = env(tmp_path)
    cfg.safety.jitter_seconds = 3600  # огромный джиттер
    vid = _long(db, clock, "/j")
    soon = clock.now() + timedelta(seconds=30)
    post = pub.publish("long_video", vid, "youtube", "/j/w.mp4", {"title": "x"}, soon)
    assert post is not None
    row = db.fetchone(
        "SELECT postiz_scheduled_for FROM entity_platform_status WHERE entity_type='long_video' "
        "AND entity_id=?", (vid,))
    scheduled = datetime.fromisoformat(row["postiz_scheduled_for"])
    assert scheduled >= clock.now()
