"""Проекты, этап 2: планировщик не пускает чужой проект в каналы другого проекта."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import ProjectCfg, load_config
from orchestrator.db import Database
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "p.sqlite")
    platforms = ["youtube", "telegram", "youtube_a", "youtube_b", "telegram_a"]
    db.ensure_platform_states(platforms)
    cfg = load_config(ROOT / "config.yaml")
    cfg.projects = {
        "a": ProjectCfg(title="Проект А", folders=["/video/a"]),
        "b": ProjectCfg(title="Проект Б", folders=["/video/b"]),
    }
    for key, project in (("youtube_a", "a"), ("telegram_a", "a"), ("youtube_b", "b")):
        cfg.platforms[key] = cfg.platforms["youtube"].model_copy(update={"project": project})
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))  # Mon
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, postiz, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    return db, cfg, clock, postiz, sched


def add_film(db, clock, folder="/video/a", title="Фильм"):
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, vertical_path, "
        "title_text, description_text, created_at) VALUES ('videomaker', ?, ?, ?, ?, ?, ?, ?)",
        (folder, title, f"{folder}/wide.mp4", f"{folder}/vert.mp4", title, "Описание",
         clock.now().isoformat()),
    )
    return db.fetchone("SELECT id FROM long_videos ORDER BY id DESC LIMIT 1")["id"]


def add_short(db, clock, folder="/video/a", parent=None, order=1):
    db.execute(
        "INSERT INTO shorts (parent_video_id, order_index, folder_path, video_path, "
        "source, title_text, description_text, created_at) VALUES (?, ?, ?, ?, 'shortsmaker', "
        "'Шортс', 'Описание', ?)",
        (parent, order, folder, f"{folder}/s{order}.mp4", clock.now().isoformat()),
    )
    return db.fetchone("SELECT id FROM shorts ORDER BY id DESC LIMIT 1")["id"]


def test_platform_ok_resolves_by_folder_and_parent(env):
    db, cfg, clock, postiz, sched = env
    film_a = add_film(db, clock, "/video/a")
    film_b = add_film(db, clock, "/video/b")
    short_b = add_short(db, clock, "/video/b", order=1)
    thematic_a = add_short(db, clock, "/video/a/shorts", parent=film_a, order=2)

    assert sched._platform_ok("youtube_a", etype="long_video", eid=film_a)
    assert not sched._platform_ok("youtube_b", etype="long_video", eid=film_a)
    assert sched._platform_ok("youtube_b", etype="long_video", eid=film_b)
    assert sched._platform_ok("youtube_b", folder="/video/b")
    assert not sched._platform_ok("youtube_b", folder="/video/a")
    # шортс серии определяется по фильму-родителю, а не по папке шортсов
    assert sched._platform_ok("youtube_a", etype="short", eid=thematic_a)
    assert not sched._platform_ok("youtube_b", etype="short", eid=thematic_a)
    # обычный шортс — по своей папке
    assert sched._platform_ok("youtube_b", etype="short", eid=short_b)
    # платформа без проекта принимает всех
    assert sched._platform_ok("youtube", etype="long_video", eid=film_a)
    assert sched._platform_ok("youtube", etype="short", eid=short_b)


def test_thematic_shorts_of_foreign_project_are_skipped(env):
    db, cfg, clock, postiz, sched = env
    film_b = add_film(db, clock, "/video/b")
    add_short(db, clock, "/video/b/shorts", parent=film_b, order=1)
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "release_url, published_at) VALUES ('long_video', ?, 'youtube_b', 'published', "
        "'https://youtu.be/x', ?)", (film_b, clock.now().isoformat()))
    assert sched.schedule_thematic_shorts(film_b, "youtube_a") == 0
    # а в свою сеть — ставится
    assert sched.schedule_thematic_shorts(film_b, "youtube_b") >= 1


def test_long_video_goes_only_to_its_project(env):
    db, cfg, clock, postiz, sched = env
    film_a = add_film(db, clock, "/video/a")
    sched.schedule_long_videos()
    rows = db.fetchall(
        "SELECT platform FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=?",
        (film_a,))
    used = {r["platform"] for r in rows}
    assert "youtube_a" in used or "youtube" in used
    assert "youtube_b" not in used


def test_standalone_short_goes_only_to_its_project(env):
    db, cfg, clock, postiz, sched = env
    short_a = add_short(db, clock, "/video/a", order=1)
    short_b = add_short(db, clock, "/video/b", order=2)
    sched.schedule_standalone_shorts()
    for sid, own, foreign in ((short_a, "youtube_a", "youtube_b"),
                              (short_b, "youtube_b", "youtube_a")):
        used = {r["platform"] for r in db.fetchall(
            "SELECT platform FROM entity_platform_status WHERE entity_type='short' AND entity_id=?",
            (sid,))}
        assert foreign not in used, (sid, used)
        assert own in used or "youtube" in used, (sid, used)


def test_telegram_links_skip_foreign_project(env):
    db, cfg, clock, postiz, sched = env
    cfg.platforms["telegram"].project = "a"   # канал привязан к проекту А
    film_b = add_film(db, clock, "/video/b")
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "release_url, postiz_scheduled_for, published_at) VALUES ('long_video', ?, 'youtube', "
        "'published', 'https://youtu.be/x', ?, ?)",
        (film_b, clock.now().isoformat(), clock.now().isoformat()))
    assert sched.schedule_telegram_links() == 0
    assert db.fetchone(
        "SELECT 1 FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=? "
        "AND platform='telegram'", (film_b,)) is None
