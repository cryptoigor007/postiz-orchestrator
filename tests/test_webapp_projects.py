"""Проекты, этап 3 (API): список проектов и проект у каждой строки панели."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import ProjectCfg, load_config
from orchestrator.db import Database
from orchestrator.webapp_api import WebAppAPI

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "w.sqlite")
    db.ensure_platform_states(["youtube", "telegram"])
    cfg = load_config(ROOT / "config.yaml")
    cfg.projects = {
        "a": ProjectCfg(title="Проект А", folders=["/video/a"]),
        "b": ProjectCfg(title="Проект Б", folders=["/video/b"]),
    }
    cfg.default_project = "a"
    cfg.platforms["telegram_b"] = cfg.platforms["telegram"].model_copy(update={"project": "b"})
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))
    api = WebAppAPI({"cfg": cfg, "db": db})
    return api, db, cfg, clock


def add_film(db, clock, folder, title="Фильм"):
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, created_at) "
        "VALUES ('videomaker', ?, ?, ?, ?)", (folder, title, title, clock.now().isoformat()))
    return db.fetchone("SELECT id FROM long_videos ORDER BY id DESC LIMIT 1")["id"]


def test_projects_endpoint_counts_by_project(env):
    api, db, cfg, clock = env
    film_a = add_film(db, clock, "/video/a", "Свой")
    film_b = add_film(db, clock, "/video/b", "Чужой")
    when = clock.now().isoformat()
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', ?, 'youtube', 'scheduled', ?)", (film_a, when))
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', ?, 'youtube', 'scheduled', ?)", (film_b, when))

    data = api._projects()
    assert data["default"] == "a"
    by_id = {p["id"]: p for p in data["items"]}
    assert by_id["a"]["title"] == "Проект А"
    assert by_id["a"]["counts"].get("scheduled") == 1
    assert by_id["b"]["counts"].get("scheduled") == 1
    assert "telegram_b" in by_id["b"]["platforms"]
    assert "" not in by_id  # с default_project «без проекта» не остаётся


def test_queue_rows_carry_project(env):
    api, db, cfg, clock = env
    film_a = add_film(db, clock, "/video/a")
    film_b = add_film(db, clock, "/video/b")
    when = clock.now().isoformat()
    for film in (film_a, film_b):
        db.execute(
            "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
            "last_error, postiz_scheduled_for) VALUES "
            "('long_video', ?, 'telegram', 'ready', 'waiting_for_youtube', ?)", (film, when))

    items = {i["entity_id"]: i for i in api._queue()["items"]}
    assert items[film_a]["project"] == "a"
    assert items[film_b]["project"] == "b"


def test_calendar_and_failed_rows_carry_project(env):
    api, db, cfg, clock = env
    film_b = add_film(db, clock, "/video/b", "Чужой")
    when = clock.now().isoformat()
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "postiz_scheduled_for) VALUES ('long_video', ?, 'youtube', 'error', ?)", (film_b, when))
    days = api._calendar()["days"]
    cal = [i for d in days for i in d["items"]]
    assert cal and cal[0]["project"] == "b"
    failed = api._failed()["items"]
    assert failed and failed[0]["project"] == "b"
