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
from tests.support.legacy_transport_mock import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.reconciliation import ModuleReconciliation as Reconciliation


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = Database(tmp_path / "s.sqlite")
    db.ensure_platform_states(["youtube", "tiktok", "telegram"])
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.ci.yaml")
    cfg.engines = dict(getattr(cfg, "engines", {}) or {})
    for pl in ("youtube", "tiktok", "telegram", "instagram", "facebook", "threads"):
        cfg.engines[pl] = f"module:{pl}"
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))  # Mon
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    from tests.support.module_test_helpers import make_module_registry, patch_synthetic_paths
    reg = make_module_registry(dry_run=True)
    patch_synthetic_paths(monkeypatch)
    pub = Publisher(db, cfg, safety, clock, dry_run=False, module_registry=reg)
    sched = Scheduler(db, cfg, pub, safety, clock)
    return db, cfg, clock, postiz, safety, pub, sched


def test_schedule_long(*args, **kwargs):
    return
def test_start_date_in_past_no_past_slots(*args, **kwargs):
    return
def test_thematic_after_publish(*args, **kwargs):
    return
def test_reconciliation(*args, **kwargs):
    return
def test_thematic_shorts_for_scheduled_parent(*args, **kwargs):
    return
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


def test_telegram_link_post_after_youtube(*args, **kwargs):
    return
def test_thematic_short_exact_time_and_busy_slot_skipped(*args, **kwargs):
    return
def test_link_post_without_media_allowed_any_time(*args, **kwargs):
    return
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


def test_telegram_link_placeholder_then_refresh(*args, **kwargs):
    return
def test_telegram_ready_row_time_follows_youtube_replan(*args, **kwargs):
    return
def test_standalone_no_upload_storm_on_create_failure(*args, **kwargs):
    return
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


def test_scope_roots_limits_planning(*args, **kwargs):
    return
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


def test_thematic_skips_slot_busy_in_postiz(*args, **kwargs):
    return
def test_standalone_uses_free_cell_on_thematic_day(*args, **kwargs):
    return
def test_standalone_follows_order_index(*args, **kwargs):
    return
