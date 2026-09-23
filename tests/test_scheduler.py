from __future__ import annotations

import json
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


def test_start_date_in_past_no_past_slots(env):
    """P1-7: start_date из прошлого не должен создавать посты «в прошлом»."""
    db, cfg, clock, postiz, safety, pub, sched = env
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('videomaker', '/past', 'P', '/past/w.mp4', ?)",
        (now,),
    )
    sched.schedule_long_videos(start_date="2026-03-01")
    rows = db.fetchall(
        "SELECT postiz_scheduled_for FROM entity_platform_status "
        "WHERE entity_type='long_video' AND postiz_scheduled_for IS NOT NULL"
    )
    assert rows, "ожидался хотя бы один пост на будущий слот"
    for r in rows:
        assert datetime.fromisoformat(r["postiz_scheduled_for"]) > clock.now()


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
    # L5: without next_long horizon 7 days → up to 3 shorts
    assert n == 3
    rows = db.fetchall(
        "SELECT * FROM entity_platform_status WHERE entity_type='short' AND platform='youtube'"
    )
    assert len(rows) == 3
    assert len(postiz.posts) == 3


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
    assert n >= 1
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
    assert n == 2
    row = db.fetchone(
        "SELECT postiz_scheduled_for FROM entity_platform_status "
        "WHERE entity_type='short' AND platform='telegram' "
        "ORDER BY postiz_scheduled_for LIMIT 1")
    tz = get_tz(cfg.timezone)
    want = local_to_utc(long_dt.astimezone(tz).date(), parse_time("20:30"), cfg.timezone)
    assert row["postiz_scheduled_for"][:16] == want.isoformat()[:16]
    assert sched.schedule_thematic_shorts(lv["id"], "telegram") == 0
    assert len(db.fetchall(
        "SELECT 1 FROM entity_platform_status WHERE entity_type='short'")) == 2


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
    # у ссылок (без медиа) время свободное — проверяем, что медиа-пост с тем же временем отклоняется
    assert sched._is_canonical("telegram", datetime(2026, 3, 11, 12, 7, tzinfo=UTC)) is False


def test_telegram_link_placeholder_then_refresh(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    cfg.platforms["telegram"].post_mode = "link"
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, "
        "description_text, created_at) VALUES ('videomaker', '/pl', 'PL', 'Заголовок', "
        "'Описание', ?)",
        (now,),
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    # YouTube-фильм запланирован (ещё не вышел)
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', ?, 'youtube', 'scheduled', "
        "'2026-03-12T13:00:00+00:00')",
        (lv["id"],),
    )
    # пре-план: строка видна в очереди, но Postiz-пост НЕ создаётся (нет ссылки)
    n = sched.schedule_telegram_links()
    assert n == 1
    row = db.fetchone(
        "SELECT status, postiz_scheduled_for, postiz_post_id FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='telegram'",
        (lv["id"],),
    )
    assert row["status"] == "ready"
    assert row["postiz_post_id"] in (None, "")
    assert postiz.posts == {}  # ничего не публиковали
    # время = премьера + 15 минут
    from datetime import datetime as _dt
    t = _dt.fromisoformat(row["postiz_scheduled_for"])
    assert t.strftime("%H:%M") == "13:15"

    # фильм вышел: появилась ссылка -> пост пересоздаётся с реальной ссылкой
    db.execute(
        "UPDATE entity_platform_status SET status='published', "
        "release_url='https://youtu.be/xyz', published_at=? "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='youtube'",
        (now, lv["id"]),
    )
    n2 = sched.refresh_telegram_links()
    assert n2 == 1
    assert any("youtu.be/xyz" in str(p.content) for p in postiz.posts.values())
    # повторно не обновляем
    assert sched.refresh_telegram_links() == 0


def test_telegram_ready_row_time_follows_youtube_replan(env):
    db, cfg, clock, postiz, safety, pub, sched = env
    cfg.platforms["telegram"].post_mode = "link"
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, "
        "description_text, created_at) VALUES ('videomaker', '/pl2', 'PL2', 'T', 'D', ?)",
        (now,),
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', ?, 'youtube', 'scheduled', "
        "'2026-03-12T13:00:00+00:00')",
        (lv["id"],),
    )
    sched.schedule_telegram_links()
    # YouTube переехал на неделю вперёд
    db.execute(
        "UPDATE entity_platform_status SET postiz_scheduled_for='2026-03-19T13:00:00+00:00' "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='youtube'",
        (lv["id"],),
    )
    sched.schedule_telegram_links()
    row = db.fetchone(
        "SELECT postiz_scheduled_for FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='telegram'",
        (lv["id"],),
    )
    from datetime import datetime as _dt
    t = _dt.fromisoformat(row["postiz_scheduled_for"])
    assert t.strftime("%m-%d %H:%M") == "03-19 13:15"


def test_standalone_no_upload_storm_on_create_failure(env):
    """P1-6: ошибка create не приводит к шторму загрузок — одна попытка и кулдаун."""
    db, cfg, clock, postiz, safety, pub, sched = env
    db.execute(
        "INSERT INTO shorts (source, folder_path, order_index, video_path, title_text, created_at) "
        "VALUES ('shortsmaker','/sm/s0',0,'/sm/s0/v.mp4','S',?)",
        (clock.now().isoformat(),),
    )
    postiz.fail_create = True
    sched.schedule_standalone_shorts(None)
    first = len(postiz._orphan_media)
    assert first >= 1
    for _ in range(3):  # следующие циклы — в кулдауне, новых попыток нет
        clock.advance(minutes=5)
        sched.schedule_standalone_shorts(None)
    assert len(postiz._orphan_media) == first
    clock.advance(minutes=31)  # кулдаун истёк — попытка снова
    sched.schedule_standalone_shorts(None)
    assert len(postiz._orphan_media) > first


def test_platform_package_paths_are_strict(env):
    """Пакеты платформ: чужая платформа файл не получает (подстановки wide/vertical нет)."""
    db, cfg, clock, postiz, safety, pub, sched = env
    row = {
        "platform_paths": json.dumps({"youtube": "/s1/youtube/wide/final_16x9.mp4"}),
        "wide_path": "/s1/youtube/wide/final_16x9.mp4",
        "vertical_path": None,
        "video_path": None,
    }
    assert sched._pick_path(row, "youtube", cfg.platforms["youtube"]).endswith("final_16x9.mp4")
    assert sched._pick_path(row, "telegram", cfg.platforms["telegram"]) is None
    assert sched._pick_path(row, "tiktok", cfg.platforms["tiktok"]) is None

    # старый формат (карта пустая) — как раньше: wide/vertical по формату платформы
    legacy = {
        "platform_paths": None,
        "wide_path": "/s1/wide/final_16x9.mp4",
        "vertical_path": "/s1/vertical/final_9x16.mp4",
        "video_path": None,
    }
    assert sched._pick_path(legacy, "youtube", cfg.platforms["youtube"]).endswith(
        "wide/final_16x9.mp4")
    assert sched._pick_path(legacy, "telegram", cfg.platforms["telegram"]).endswith(
        "vertical/final_9x16.mp4")

    # шортс из пакета не уезжает на чужую платформу
    packed_short = {
        "platform_paths": json.dumps({"youtube": "/s1/short.mp4"}),
        "video_path": "/s1/short.mp4",
        "wide_path": None,
        "vertical_path": None,
    }
    assert sched._pick_short_path(packed_short, "youtube") == "/s1/short.mp4"
    assert sched._pick_short_path(packed_short, "telegram") is None
    legacy_short = {"platform_paths": None, "video_path": "/s1/short.mp4"}
    assert sched._pick_short_path(legacy_short, "telegram") == "/s1/short.mp4"


def test_scope_roots_limits_planning(env):
    """«Запустить» планирует только то, что лежит в «Папках для сканирования»."""
    db, cfg, clock, postiz, safety, pub, sched = env
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) VALUES "
        "('videomaker', '/mnt/video/broll_downloads/7', 'New', '/7/youtube/wide/final_16x9.mp4', ?)",
        (now,))
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) VALUES "
        "('videomaker', '/mnt/video/ssd_backup/old/01', 'Old', '/old/wide/final_16x9.mp4', ?)",
        (now,))
    n = sched.schedule_long_videos(scope_roots=["/mnt/video/broll_downloads/7"])
    assert n == 1
    rows = db.fetchall(
        "SELECT entity_id, platform FROM entity_platform_status WHERE entity_type='long_video'")
    assert len(rows) == 1
    film = db.fetchone(
        "SELECT id FROM long_videos WHERE folder_path='/mnt/video/broll_downloads/7'")
    assert rows[0]["entity_id"] == film["id"]

    # отдельные шортсы вне области сканирования не планируются
    db.execute(
        "INSERT INTO shorts (source, folder_path, video_path, created_at) VALUES "
        "('shortsmaker', '/mnt/video/ssd_backup/old/12/shorts/s1::s1.mp4', "
        "'/mnt/video/ssd_backup/old/12/shorts/s1.mp4', ?)", (now,))
    n2 = sched.schedule_standalone_shorts(None, scope_roots=["/mnt/video/broll_downloads/7"])
    assert n2 == 0


def test_scope_roots_filters_thematic_shorts_of_other_folders(env):
    """Шортсы фильма вне «Папок для сканирования» не планируются."""
    db, cfg, clock, postiz, safety, pub, sched = env
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) VALUES "
        "('videomaker', '/mnt/video/ssd_backup/old/01', 'Old', '/old/wide/final_16x9.mp4', ?)",
        (now,))
    fid = int(db.fetchone("SELECT id FROM long_videos ORDER BY id DESC")["id"])
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
        "VALUES ('long_video', ?, 'youtube', 'scheduled')", (fid,))
    db.execute(
        "INSERT INTO shorts (source, parent_video_id, folder_path, video_path, created_at) "
        "VALUES ('videomaker', ?, '/old/shorts/s1', '/old/shorts/s1.mp4', ?)", (fid, now))
    assert sched.schedule_thematic_shorts(
        fid, "youtube", scope_roots=["/mnt/video/broll_downloads/7"]) == 0


def test_thematic_skips_slot_busy_in_postiz(env):
    """Слот, занятый постом в Postiz, пропускается — шортс уходит на следующий, без safety_block."""
    db, cfg, clock, postiz, safety, pub, sched = env
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('videomaker', '/s9', 'S9', '/s9/w.mp4', ?)", (now,))
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/s9'")["id"]
    pub_time = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)  # вт, 19:00 МСК
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status,"
        " postiz_post_id, postiz_scheduled_for, published_at, release_url)"
        " VALUES ('long_video', ?, 'youtube', 'published', 'p1', ?, ?, 'https://youtu.be/x')",
        (vid, pub_time.isoformat(), pub_time.isoformat()))
    db.execute(
        "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, video_path,"
        " title_text, description_text, created_at)"
        " VALUES ('videomaker', ?, '/s9/shorts/s0', 0, '/s9/shorts/s0/v.mp4', 'S', 'D', ?)",
        (vid, now))

    # в Postiz уже занят первый слот 20:30 МСК = 17:30 UTC того же дня
    from orchestrator.schedule_guard import ScheduleGuard
    busy = [datetime(2026, 3, 10, 17, 30, tzinfo=UTC)]
    pub.guard = ScheduleGuard(cfg, clock, sources=[("postiz", lambda p: busy)])

    assert sched.schedule_thematic_shorts(vid, "youtube") == 1
    row = db.fetchone(
        "SELECT postiz_scheduled_for FROM entity_platform_status"
        " WHERE entity_type='short' AND platform='youtube'")
    got = datetime.fromisoformat(row["postiz_scheduled_for"])
    assert got == datetime(2026, 3, 11, 17, 30, tzinfo=UTC), got
    blocks = db.fetchall("SELECT id FROM publish_log WHERE action='safety_block'")
    assert blocks == []


def test_standalone_uses_free_cell_on_thematic_day(env):
    """Пустые ячейки: 12:00/18:00 на дне шортса серии (20:30) свободны — ставим обычный шортс."""
    db, cfg, clock, postiz, safety, pub, sched = env
    clock.set(datetime(2026, 3, 10, 10, 0, tzinfo=UTC))  # вт, 13:00 МСК
    now = clock.now().isoformat()
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, created_at) "
        "VALUES ('videomaker','/s','S','/s/w.mp4',?)", (now,))
    lv = db.fetchone("SELECT id FROM long_videos")["id"]
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status,"
        " postiz_scheduled_for) VALUES ('long_video', ?, 'youtube', 'scheduled', ?)",
        (lv, "2026-03-10T13:00:00+00:00"),
    )
    db.execute(
        "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, video_path,"
        " title_text, created_at) VALUES ('videomaker', ?, '/s/shorts/short_001', 0,"
        " '/s/shorts/short_001/v.mp4', 'S1', ?)", (lv, now))
    sid = db.fetchone("SELECT id FROM shorts")["id"]
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status,"
        " postiz_scheduled_for) VALUES ('short', ?, 'youtube', 'scheduled', ?)",
        (sid, "2026-03-11T17:30:00+00:00"),  # ср 20:30 МСК — день занят шортсом серии
    )
    db.execute(
        "INSERT INTO shorts (source, folder_path, order_index, video_path, title_text, created_at)"
        " VALUES ('shortsmaker','/sm/ш1',0,'/sm/ш1/v.mp4','Ш1',?)", (now,))
    alone = db.fetchone("SELECT id FROM shorts WHERE source='shortsmaker'")["id"]
    assert sched.schedule_standalone_shorts(None) == 1
    row = db.fetchone(
        "SELECT postiz_scheduled_for FROM entity_platform_status"
        " WHERE entity_type='short' AND entity_id=? AND platform='youtube'", (alone,))
    assert row["postiz_scheduled_for"] == "2026-03-11T09:00:00+00:00"  # ср 12:00 МСК, ячейка свободна


def test_standalone_follows_order_index(env):
    """Порядок раскладки — по нумерации в папке (order_index), а не по времени регистрации."""
    db, cfg, clock, postiz, safety, pub, sched = env
    now = clock.now().isoformat()
    for title, idx, path in (("второй", 1, "/sm/b"), ("первый", 0, "/sm/a")):
        db.execute(
            "INSERT INTO shorts (source, folder_path, order_index, video_path, title_text,"
            " created_at) VALUES ('shortsmaker', ?, ?, ?, ?, ?)",
            (path, idx, path + "/v.mp4", title, now),
        )
    assert sched.schedule_standalone_shorts(None) == 2
    rows = db.fetchall(
        "SELECT s.title_text t, e.postiz_scheduled_for p FROM entity_platform_status e"
        " JOIN shorts s ON s.id = e.entity_id"
        " WHERE e.entity_type='short' AND e.platform='youtube' ORDER BY e.postiz_scheduled_for")
    assert [r["t"] for r in rows] == ["первый", "второй"]
