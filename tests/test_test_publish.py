"""Тесты пробного поста (test_publish): отдельный контур, боевая сетка не затрагивается."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock  # noqa: E402
from orchestrator.config import load_config  # noqa: E402
from orchestrator.db import Database  # noqa: E402
from orchestrator.postiz import MockPostizClient  # noqa: E402
from orchestrator.safety import SafetyChecker  # noqa: E402
from orchestrator.test_publish import (  # noqa: E402
    TestPublishError,
    cancel_test_post,
    schedule_test_post,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "tp.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    cfg.test_publish.enabled = True
    cfg.test_publish.platforms = ["youtube"]
    cfg.test_publish.require_explicit_platforms = True
    cfg.test_publish.default_delay_minutes = 1
    clock = FakeClock(datetime(2026, 9, 21, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    safety = SafetyChecker(db, cfg, clock)
    comps = {"cfg": cfg, "db": db, "clock": clock, "postiz": postiz,
             "safety": safety, "broker": None}
    now = clock.now().isoformat()
    db.execute("INSERT INTO shorts (source, folder_path, video_path, title_text, "
               "description_text, hashtags_text, created_at) "
               "VALUES ('shortsmaker', '/s', '/tmp/s.mp4', 'Заголовок', 'Описание', '#tag', ?)",
               (now,))
    sid = db.fetchone("SELECT id FROM shorts ORDER BY id DESC")["id"]
    return comps, db, cfg, clock, postiz, sid


def test_disabled_raises(tmp_path):
    db = Database(tmp_path / "d.sqlite")
    cfg = load_config(ROOT / "config.yaml")
    cfg.test_publish.enabled = False
    clock = FakeClock(datetime(2026, 9, 21, 12, 0, tzinfo=UTC))
    comps = {"cfg": cfg, "db": db, "clock": clock, "postiz": MockPostizClient()}
    db.execute("INSERT INTO shorts (source, folder_path, video_path, created_at) "
               "VALUES ('shortsmaker', '/s', '/tmp/s.mp4', ?)", (clock.now().isoformat(),))
    sid = db.fetchone("SELECT id FROM shorts")["id"]
    with pytest.raises(TestPublishError) as e:
        schedule_test_post(comps, platform="youtube", entity_type="short", entity_id=sid)
    assert e.value.code == 403


def test_platform_allowlist_enforced(env):
    comps, db, cfg, clock, postiz, sid = env
    with pytest.raises(TestPublishError) as e:
        schedule_test_post(comps, platform="telegram", entity_type="short", entity_id=sid)
    assert e.value.code == 403 and "allowlist" in str(e.value)


def test_delay_bounds(env):
    comps, db, cfg, clock, postiz, sid = env
    for bad in (0, 121):
        with pytest.raises(TestPublishError) as e:
            schedule_test_post(comps, platform="youtube", entity_type="short",
                               entity_id=sid, delay_minutes=bad)
        assert e.value.code == 400


def test_default_delay_one_minute_and_prefix_and_no_row_touch(env):
    comps, db, cfg, clock, postiz, sid = env
    res = schedule_test_post(comps, platform="youtube", entity_type="short", entity_id=sid)
    assert res["ok"] and res["dry_run"] is False
    when = datetime.fromisoformat(res["scheduled_for"])
    assert abs((when - clock.now()).total_seconds() - 60) < 2
    posts = list(postiz.posts.values())
    assert len(posts) == 1
    assert posts[0].content["title"].startswith("[orch-test] ")
    # БОЕВАЯ СЕТКА НЕ ЗАТРОНУТА: строк в entity_platform_status нет
    assert db.fetchone("SELECT COUNT(*) AS c FROM entity_platform_status")["c"] == 0
    # факт зафиксирован в журнале
    lg = db.fetchall("SELECT action FROM publish_log WHERE action='test_scheduled'")
    assert len(lg) == 1


def test_explicit_scheduled_for_past_rejected(env):
    comps, db, cfg, clock, postiz, sid = env
    past = (clock.now() - timedelta(minutes=5)).isoformat()
    with pytest.raises(TestPublishError) as e:
        schedule_test_post(comps, platform="youtube", entity_type="short",
                           entity_id=sid, scheduled_for=past)
    assert e.value.code == 400


def test_telegram_large_file_rejected(env, tmp_path):
    comps, db, cfg, clock, postiz, sid = env
    cfg.platforms["telegram"].post_mode = "media"
    big = tmp_path / "big.mp4"
    big.write_bytes(b"0" * (46 * 1024 * 1024))
    db.execute("UPDATE shorts SET video_path=? WHERE id=?", (str(big), sid))
    # youtube большим файлом не ограничен
    res = schedule_test_post(comps, platform="youtube", entity_type="short", entity_id=sid)
    assert res["ok"] is True
    cfg.test_publish.platforms = ["youtube", "telegram"]
    with pytest.raises(TestPublishError) as e:
        schedule_test_post(comps, platform="telegram", entity_type="short", entity_id=sid)
    assert e.value.code == 400 and "45" in str(e.value)


def test_link_mode_uses_youtube_url(env):
    comps, db, cfg, clock, postiz, sid = env
    cfg.test_publish.platforms = ["youtube", "telegram"]
    db.execute("INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
               "release_url) VALUES ('short', ?, 'youtube', 'published', "
               "'https://www.youtube.com/watch?v=TEST123')", (sid,))
    res = schedule_test_post(comps, platform="telegram", entity_type="short", entity_id=sid)
    assert res["ok"] is True
    post = list(postiz.posts.values())[0]
    assert "https://www.youtube.com/watch?v=TEST123" in post.content["description"]
    assert post.content["description"].startswith("[orch-test] ")
    assert postiz.media == {}  # медиа не загружалось (link-режим)


def test_link_mode_without_url_rejected(env):
    comps, db, cfg, clock, postiz, sid = env
    cfg.test_publish.platforms = ["youtube", "telegram"]
    with pytest.raises(TestPublishError) as e:
        schedule_test_post(comps, platform="telegram", entity_type="short", entity_id=sid)
    assert e.value.code == 400 and "YouTube" in str(e.value)


def test_entity_not_found(env):
    comps, db, cfg, clock, postiz, sid = env
    with pytest.raises(TestPublishError) as e:
        schedule_test_post(comps, platform="youtube", entity_type="short", entity_id=999999)
    assert e.value.code == 404


def test_dry_run_creates_nothing(env):
    comps, db, cfg, clock, postiz, sid = env
    res = schedule_test_post(comps, platform="youtube", entity_type="short",
                             entity_id=sid, dry_run=True)
    assert res["dry_run"] is True and postiz.posts == {}
    assert db.fetchone("SELECT COUNT(*) AS c FROM entity_platform_status")["c"] == 0
    assert db.fetchall("SELECT 1 FROM publish_log WHERE action='test_dry_run'")


def test_prod_channel_guard(env):
    comps, db, cfg, clock, postiz, sid = env
    cfg.test_publish.prod_integration_ids = [cfg.platforms["youtube"].integration_id]
    with pytest.raises(TestPublishError) as e:
        schedule_test_post(comps, platform="youtube", entity_type="short", entity_id=sid)
    assert e.value.code == 403 and "prod" in str(e.value)
    cfg.test_publish.allow_prod_channel = True
    res = schedule_test_post(comps, platform="youtube", entity_type="short", entity_id=sid)
    assert res["ok"] is True


def test_cancel_only_test_posts(env):
    comps, db, cfg, clock, postiz, sid = env
    res = schedule_test_post(comps, platform="youtube", entity_type="short", entity_id=sid)
    pid = res["postiz_post_id"]
    assert pid in postiz.posts
    out = cancel_test_post(comps, pid)
    assert out["ok"] and pid not in postiz.posts
    assert db.fetchall("SELECT 1 FROM publish_log WHERE action='test_cancelled'")
    with pytest.raises(TestPublishError) as e:
        cancel_test_post(comps, "nonexistent")
    assert e.value.code == 404


# --- API-уровень ---

def _api(env):
    from orchestrator.webapp_api import WebAppAPI

    comps, db, cfg, clock, postiz, sid = env
    return WebAppAPI(comps), db, sid


def test_api_test_schedule_and_status(env):
    api, db, sid = _api(env)
    headers = {"X-Telegram-Init-Data": "dev"}
    code, payload, _ = api.handle("GET", "/webapp/api/test/status", headers, b"")
    assert code == 200 and payload["enabled"] is True and "youtube" in payload["platforms"]
    body = json.dumps({"platforms": ["youtube"], "delay_minutes": 1,
                       "entity_type": "short", "entity_id": sid}).encode()
    code, payload, _ = api.handle("POST", "/webapp/api/test/schedule", headers, body)
    assert code == 200 and payload["postiz_post_id"]
    code, payload, _ = api.handle("POST", "/webapp/api/test/cancel", headers,
                                  json.dumps({"postiz_post_id": payload["postiz_post_id"]}).encode())
    assert code == 200 and payload["deleted"]


def test_api_test_schedule_validation(env):
    api, db, sid = _api(env)
    headers = {"X-Telegram-Init-Data": "dev"}
    code, payload, _ = api.handle("POST", "/webapp/api/test/schedule", headers,
                                  json.dumps({"platform": "telegram", "entity_id": sid}).encode())
    assert code == 403  # не в allowlist
    code, payload, _ = api.handle("POST", "/webapp/api/test/schedule", headers, b"{}")
    assert code == 400


def test_api_read_only_blocks_test_schedule(env, monkeypatch):
    api, db, sid = _api(env)
    monkeypatch.setenv("ORCH_READ_ONLY", "1")
    headers = {"X-Telegram-Init-Data": "dev"}
    code, payload, _ = api.handle("POST", "/webapp/api/test/schedule", headers,
                                  json.dumps({"platform": "youtube", "entity_id": sid}).encode())
    assert code == 403 and payload.get("error") == "read_only"


def test_sql_injection_in_queue_edit_has_no_effect(tmp_path):
    """Параметризация: инъекция не должна удалить таблицу."""
    db = Database(tmp_path / "sqli.sqlite")
    now = datetime.now(UTC).isoformat()
    db.execute("INSERT INTO shorts (source, folder_path, title_text, created_at) "
               "VALUES ('shortsmaker', '/s', 't', ?)", (now,))
    db.execute("UPDATE shorts SET title_text=? WHERE id=1",
               ("x'); DROP TABLE shorts;--",))
    row = db.fetchone("SELECT title_text FROM shorts WHERE id=1")
    assert "DROP TABLE" in row["title_text"]
    assert db.fetchone("SELECT COUNT(*) AS c FROM sqlite_master "
                       "WHERE type='table' AND name='shorts'")["c"] == 1
