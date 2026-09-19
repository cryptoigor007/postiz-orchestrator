from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.status_sync import Reconciliation


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "s.sqlite")
    db.ensure_platform_states(["youtube", "tiktok"])
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))  # Mon
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    return db, cfg, clock, postiz, safety, pub, sched


def test_schedule_long(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, vertical_path, "
        "title_text, description_text, created_at) VALUES "
        "('videomaker', '/series1', 'S1', '/series1/wide.mp4', '/series1/vert.mp4', "
        "'Title', 'Desc', ?)",
        (now,),
    )
    n = sched.schedule_long_videos()
    assert n >= 1
    rows = db.fetchall(
        "SELECT * FROM entity_platform_status WHERE entity_type='long_video'"
    )
    assert len(rows) >= 1
    assert rows[0]["status"] == "scheduled"
    assert rows[0]["postiz_post_id"] is not None


def test_thematic_after_publish(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('videomaker', '/s2', 'S2', '/s2/w.mp4', ?)",
        (now,),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/s2'")["id"]
    # mark as published with url
    pub_time = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    db.execute(
        """
        INSERT INTO entity_platform_status
            (entity_type, entity_id, platform, status, postiz_post_id,
             postiz_scheduled_for, published_at, release_url)
        VALUES ('long_video', ?, 'youtube', 'published', 'p1', ?, ?, ?)
        """,
        (vid, pub_time.isoformat(), pub_time.isoformat(), "https://youtu.be/abc"),
    )
    # add shorts
    for i in range(3):
        db.execute(
            """
            INSERT INTO shorts (source, parent_video_id, folder_path, order_index,
                video_path, title_text, description_text, created_at)
            VALUES ('videomaker', ?, ?, ?, ?, ?, ?, ?)
            """,
            (vid, f"/s2/shorts/s{i}", i, f"/s2/shorts/s{i}/v.mp4",
             f"Short {i}", f"Desc {i}", now),
        )
    n = sched.schedule_thematic_shorts(vid, "youtube")
    # один шорт на день-слот (ровно в 20:30); в окне один день -> один шорт
    assert n == 1
    rows = db.fetchall(
        "SELECT * FROM entity_platform_status WHERE entity_type='short' AND platform='youtube'"
    )
    assert len(rows) == 1
    assert len(postiz.posts) == 1


def test_reconciliation(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    recon = Reconciliation(db, postiz, clock)
    # create a post in postiz that we don't know
    from orchestrator.postiz import PostizPost
    postiz.posts["orphan1"] = PostizPost(
        id="orphan1", platform="youtube",
        scheduled_for=clock.now(), status="scheduled"
    )
    r = recon.run()
    assert r["orphans"] == 1


def test_thematic_shorts_for_scheduled_parent(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    cfg.platforms["telegram"].post_mode = "media"
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, vertical_path, "
        "title_text, created_at) VALUES ('videomaker', '/s1', 'S1', '/s1/v.mp4', 'T', ?)",
        (now,),
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    for i in range(1, 3):
        db.execute(
            "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, "
            "video_path, title_text, created_at) VALUES ('videomaker', ?, ?, ?, ?, ?, ?)",
            (lv["id"], f"/s1/shorts/short_00{i}", i, f"/s1/shorts/short_00{i}/s{i}.mp4",
             f"Шорт {i}", now),
        )
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', ?, 'telegram', 'scheduled', "
        "'2026-03-10T13:00:00+00:00')",
        (lv["id"],),
    )
    n = sched.schedule_thematic_shorts(lv["id"], "telegram")
    assert n == 1
    rows = db.fetchall(
        "SELECT status FROM entity_platform_status WHERE entity_type='short'")
    assert rows and all(r["status"] == "scheduled" for r in rows)


def test_pick_path_variants(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    row = {"wide_path": "/w.mp4", "vertical_path": "/v.mp4", "platform_paths": None}
    assert sched._pick_path(row, "youtube", cfg.platforms["youtube"]) == "/w.mp4"
    assert sched._pick_path(row, "telegram", cfg.platforms["telegram"]) == "/v.mp4"


def test_auth_error_pauses_platform(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    cfg.platforms["telegram"].post_mode = "media"
    platform = "telegram"
    db.ensure_platform_states([platform])

    def boom(*a, **k):
        raise RuntimeError("401 Unauthorized: token expired")

    pub.publish = boom
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, vertical_path, "
        "title_text, created_at) VALUES ('videomaker', '/sx', 'SX', '/sx/v.mp4', 'T', ?)",
        (clock.now().isoformat(),),
    )
    n = sched.schedule_long_videos()
    assert n == 0
    assert safety.is_platform_paused(platform) is True


def test_telegram_link_post_after_youtube(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    cfg.platforms["telegram"].post_mode = "link"
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, "
        "description_text, hashtags_text, created_at) "
        "VALUES ('videomaker', '/lk', 'LK', 'Заголовок', 'Описание', '#тег', ?)",
        (now,),
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_post_id, release_url, published_at) VALUES ('long_video', ?, 'youtube', "
        "'published', 'p1', 'https://youtu.be/abc', ?)",
        (lv["id"], now),
    )
    n = sched.schedule_telegram_links()
    assert n == 1
    row_t = db.fetchone(
        "SELECT postiz_scheduled_for FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='telegram'",
        (lv["id"],),
    )
    # время = сейчас + задержка (15 мин), не привязывается к слотам
    from datetime import datetime as _dt
    t = _dt.fromisoformat(row_t["postiz_scheduled_for"])
    assert 10 <= (t - clock.now()).total_seconds() / 60 <= 20
    row = db.fetchone(
        "SELECT status, postiz_post_id FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='telegram'",
        (lv["id"],),
    )
    assert row is not None and row["postiz_post_id"]
    # повторно не создаём
    assert sched.schedule_telegram_links() == 0


def test_thematic_short_exact_time_and_busy_slot_skipped(env):
    from orchestrator.slots import get_tz, local_to_utc, parse_time

    db, cfg, clock, postiz, safety, pub, sched = env
    cfg.platforms["telegram"].post_mode = "media"
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, created_at) "
        "VALUES ('videomaker', '/ex', 'EX', 'T', ?)",
        (now,),
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    for i in (1, 2):
        db.execute(
            "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, "
            "video_path, title_text, created_at) VALUES "
            "('videomaker', ?, ?, ?, ?, ?, ?)",
            (lv["id"], f"/ex/shorts/s{i}", i, f"/ex/shorts/s{i}/v.mp4", f"S{i}", now),
        )
    long_dt = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', ?, 'telegram', 'scheduled', ?)",
        (lv["id"], long_dt.isoformat()),
    )
    n = sched.schedule_thematic_shorts(lv["id"], "telegram")
    assert n == 1  # ровно один слот 20:30
    row = db.fetchone(
        "SELECT postiz_scheduled_for FROM entity_platform_status "
        "WHERE entity_type='short' AND platform='telegram'")
    tz = get_tz(cfg.timezone)
    want = local_to_utc(long_dt.astimezone(tz).date(), parse_time("20:30"), cfg.timezone)
    assert row["postiz_scheduled_for"][:16] == want.isoformat()[:16]
    # повторный запуск не добавляет второй шорт в тот же слот (без сдвига на 20:55/21:20)
    assert sched.schedule_thematic_shorts(lv["id"], "telegram") == 0
    assert len(db.fetchall(
        "SELECT 1 FROM entity_platform_status WHERE entity_type='short'")) == 1


def test_link_post_without_media_allowed_any_time(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    cfg.platforms["telegram"].post_mode = "media"
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO shorts (source, folder_path, video_path, title_text, created_at) "
        "VALUES ('shortsmaker', '/sm/link', '/sm/link/v.mp4', 'S', ?)",
        (now,),
    )
    sh = db.fetchone("SELECT id FROM shorts")
    weird = datetime(2026, 3, 11, 12, 7, tzinfo=UTC)
    post = sched._safe_publish("short", sh["id"], "telegram", None,
                               {"title": "x", "description": "link"}, weird)
    assert post is not None  # ссылка без медиа — время свободное


def test_non_canonical_slot_rejected(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, vertical_path, created_at) "
        "VALUES ('videomaker', '/nc', 'NC', '/nc/v.mp4', ?)",
        (now,),
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    # 12:07 — не из расписания (разрешены 16:00, 20:30, 12:00, 18:00)
    weird = datetime(2026, 3, 11, 12, 7, tzinfo=UTC)
    assert sched._safe_publish("long_video", lv["id"], "telegram", "/nc/v.mp4",
                               {"title": "x"}, weird) is None
    # 09:00 UTC = 12:00 МСК — это канонический слот (standalone)
    assert sched._is_canonical("telegram", datetime(2026, 3, 11, 9, 0, tzinfo=UTC)) is True
    # ссылки в Telegram ставятся только в канонические слоты
    nxt = sched._next_canonical("telegram", datetime(2026, 3, 11, 12, 7, tzinfo=UTC))
    from orchestrator.slots import get_tz
    assert nxt.astimezone(get_tz(cfg.timezone)).strftime("%H:%M") in ("16:00", "18:00", "20:30")
