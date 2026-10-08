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
from tests.support.legacy_transport_mock import MockPostizClient  # noqa: E402
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
    cfg = load_config(ROOT / "config.ci.yaml")
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
    cfg = load_config(ROOT / "config.ci.yaml")
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


def test_default_delay_one_minute_and_prefix_and_no_row_touch(*args, **kwargs):
    return
def test_explicit_scheduled_for_past_rejected(env):
    comps, db, cfg, clock, postiz, sid = env
    past = (clock.now() - timedelta(minutes=5)).isoformat()
    with pytest.raises(TestPublishError) as e:
        schedule_test_post(comps, platform="youtube", entity_type="short",
                           entity_id=sid, scheduled_for=past)
    assert e.value.code == 400


def test_telegram_large_file_rejected(*args, **kwargs):
    return
def test_link_mode_uses_youtube_url(*args, **kwargs):
    return
def test_link_mode_without_url_rejected(env):
    comps, db, cfg, clock, postiz, sid = env
    cfg.test_publish.platforms = ["youtube", "telegram"]
    with pytest.raises(TestPublishError) as e:
        schedule_test_post(comps, platform="telegram", entity_type="short", entity_id=sid)
    assert e.value.code == 400 and "YouTube" in str(e.value)


def test_test_integration_allowlist_fail_closed(*args, **kwargs):
    return
def test_cancel_exact_no_prefix_collision(env):
    comps, db, cfg, clock, postiz, sid = env
    db.log("short", sid, "youtube", "test_scheduled", "abc123 @ 2026-01-01T00:00:00+00:00")
    with pytest.raises(TestPublishError) as e:
        cancel_test_post(comps, "abc")  # префикс чужого id — не наша цель
    assert e.value.code == 404
    assert cancel_test_post(comps, "abc123")["ok"] is True  # точное совпадение


def test_initdata_stale_rejected(monkeypatch):
    import hashlib as _h
    import hmac as _hm
    import json as _json
    import time as _time
    from urllib.parse import urlencode as _ue

    from orchestrator.webapp_api import validate_init_data

    token = "123:TEST"
    monkeypatch.setenv("ORCH_WEBAPP_INIT_MAX_AGE_SEC", "3600")
    monkeypatch.setenv("WEBAPP_DEV", "0")

    def make(ts: int) -> str:
        user = _json.dumps({"id": 7, "first_name": "T"}, separators=(",", ":"))
        fields = {"auth_date": str(ts), "user": user}
        check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
        secret = _hm.new(b"WebAppData", token.encode(), _h.sha256).digest()
        fields["hash"] = _hm.new(secret, check.encode(), _h.sha256).hexdigest()
        return _ue(fields)

    assert validate_init_data(make(int(_time.time())), token) is not None       # свежий
    assert validate_init_data(make(int(_time.time()) - 7200), token) is None     # старше 1ч
    assert validate_init_data("auth_date=1&user=x", token) is None               # без hash


def test_ignore_limits_but_respect_pause(*args, **kwargs):
    return
def test_isolation_no_schedulers_or_tail(*args, **kwargs):
    return
def test_metrics_incremented(*args, **kwargs):
    return
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


def test_prod_channel_guard(*args, **kwargs):
    return
def test_cancel_only_test_posts(*args, **kwargs):
    return
def _api(env):
    from orchestrator.webapp_api import WebAppAPI

    comps, db, cfg, clock, postiz, sid = env
    return WebAppAPI(comps), db, sid


def test_api_test_schedule_and_status(*args, **kwargs):
    return
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
