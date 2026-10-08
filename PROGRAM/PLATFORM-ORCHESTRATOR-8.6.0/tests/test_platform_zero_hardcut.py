"""platform-zero HARD CUT regressions (prompt DoD + A–H)."""
from __future__ import annotations

import inspect
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.clock import FakeClock  # noqa: E402
from orchestrator.config import load_config  # noqa: E402
from orchestrator.db import Database  # noqa: E402
from orchestrator.schedule_guard import eps_source  # noqa: E402
from orchestrator.test_publish import (  # noqa: E402
    TestPublishError,
    cancel_test_post,
    schedule_test_post,
)


def _cfg():
    for name in ("config.ci.yaml", "config.example.yaml"):
        path = ROOT / name
        if path.is_file():
            return load_config(path)
    raise RuntimeError("no config")


def test_config_rejects_platform_engine(tmp_path):
    raw = yaml.safe_load((ROOT / "config.ci.yaml").read_text(encoding="utf-8"))
    raw["engines"] = dict(raw.get("engines") or {})
    raw["engines"]["youtube"] = "legacy_transport"
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.dump(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(p)


def test_eps_source_ignores_legacy_scheduled_for(tmp_path):
    """Postiz-zero runtime sources use canonical scheduled_for only."""
    db = Database(tmp_path / "eps.sqlite")
    when = datetime(2026, 4, 1, 15, 0, tzinfo=UTC)
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, legacy_scheduled_for) "
        "VALUES ('short', 9, 'youtube', 'scheduled', ?)",
        (when.isoformat(),),
    )
    times = eps_source(db)("youtube")
    assert times == []


def test_queue_orders_by_scheduled_for(tmp_path):
    """Queue list uses COALESCE; module-only scheduled_for rows appear in order."""
    from orchestrator.webapp_api import WebAppAPI

    cfg = _cfg()
    db = Database(tmp_path / "q.sqlite")
    clock = FakeClock(datetime(2026, 4, 1, 12, 0, tzinfo=UTC))
    t1 = datetime(2026, 4, 1, 14, 0, tzinfo=UTC)
    t2 = datetime(2026, 4, 1, 16, 0, tzinfo=UTC)
    db.execute(
        "INSERT INTO shorts (source, folder_path, title_text, video_path, created_at) "
        "VALUES ('s', '/a', 'A', '/a.mp4', ?)",
        (clock.now().isoformat(),),
    )
    db.execute(
        "INSERT INTO shorts (source, folder_path, title_text, video_path, created_at) "
        "VALUES ('s', '/b', 'B', '/b.mp4', ?)",
        (clock.now().isoformat(),),
    )
    id_a = db.fetchone("SELECT id FROM shorts WHERE folder_path='/a'")["id"]
    id_b = db.fetchone("SELECT id FROM shorts WHERE folder_path='/b'")["id"]
    # only scheduled_for (no platform_*)
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, scheduled_for) "
        "VALUES ('short', ?, 'youtube', 'scheduled', ?)",
        (id_b, t2.isoformat()),
    )
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, scheduled_for) "
        "VALUES ('short', ?, 'youtube', 'scheduled', ?)",
        (id_a, t1.isoformat()),
    )
    api = WebAppAPI({"db": db, "cfg": cfg, "clock": clock})
    q = api._queue()
    assert len(q["items"]) >= 2
    times = [it.get("scheduled_for") or "" for it in q["items"]]
    assert times[0] <= times[1]
    assert any(it["entity_id"] == id_a for it in q["items"])


def test_telegram_bot_path_sets_external_id(tmp_path):
    """send_due_telegram_posts writes external_id, not legacy_post_id."""
    from orchestrator.scheduler import Scheduler

    cfg = _cfg()
    if "telegram" not in cfg.platforms:
        pytest.skip("no telegram platform")
    cfg.platforms["telegram"].enabled = True
    cfg.platforms["telegram"].send_via = "bot"

    db = Database(tmp_path / "tg.sqlite")
    clock = FakeClock(datetime(2026, 4, 1, 18, 0, tzinfo=UTC))
    when = clock.now() - timedelta(minutes=5)
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, title_text, wide_path, created_at) "
        "VALUES ('v', '/lv1', 'T', 'T', '/lv1.mp4', ?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos WHERE folder_path='/lv1'")["id"]
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, scheduled_for) "
        "VALUES ('long_video', ?, 'telegram', 'scheduled', ?)",
        (vid, when.isoformat()),
    )
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, release_url, published_at) "
        "VALUES ('long_video', ?, 'youtube', 'published', ?, ?)",
        (vid, "https://youtu.be/x", clock.now().isoformat()),
    )

    tg = MagicMock()
    tg.send_post.return_value = "tg-msg-42"

    class _Sch(Scheduler):
        def _bot_telegram(self):
            return tg

        def _in_publish_cooldown(self, *a, **k):
            return False

        def _telegram_post_html(self, etype, eid, url):
            return f"<b>test</b> {url or ''}"

    safety = MagicMock()
    publisher = MagicMock()
    sch = _Sch(db, cfg, publisher, safety, clock)
    n = sch.send_due_telegram_posts()
    assert n == 1
    row = db.fetchone(
        "SELECT external_id, legacy_post_id, status FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=? AND platform='telegram'",
        (vid,),
    )
    assert row["status"] == "published"
    assert row["external_id"] == "tg-msg-42"
    assert not row["legacy_post_id"]


def test_test_publish_no_platform_comp(tmp_path):
    """dry_run ok without comps['platform']; no KeyError on missing platform."""
    cfg = _cfg()
    cfg.test_publish.enabled = True
    cfg.test_publish.require_explicit_platforms = False
    cfg.test_publish.allow_prod_channel = True
    db = Database(tmp_path / "tp.sqlite")
    clock = FakeClock(datetime(2026, 4, 1, 12, 0, tzinfo=UTC))
    db.execute(
        "INSERT INTO shorts (source, folder_path, title_text, video_path, created_at) "
        "VALUES ('s', '/t1', 'T', '/t1.mp4', ?)",
        (clock.now().isoformat(),),
    )
    sid = db.fetchone("SELECT id FROM shorts WHERE folder_path='/t1'")["id"]
    comps = {"cfg": cfg, "db": db, "clock": clock}
    assert "platform" not in comps
    res = schedule_test_post(
        comps, platform="youtube", entity_type="short", entity_id=sid, dry_run=True,
    )
    assert res["ok"] is True and res["dry_run"] is True
    try:
        schedule_test_post(
            comps, platform="youtube", entity_type="short", entity_id=sid, dry_run=False,
        )
    except TestPublishError:
        pass
    except KeyError as e:
        pytest.fail(f"live path still depends on missing key: {e}")


def test_cancel_test_post_accepts_external_id_alias(tmp_path):
    cfg = _cfg()
    db = Database(tmp_path / "c.sqlite")
    clock = FakeClock(datetime(2026, 4, 1, 12, 0, tzinfo=UTC))
    db.log("short", 1, "youtube", "test_scheduled", "ext-99 @ 2026-04-01")
    comps = {"cfg": cfg, "db": db, "clock": clock}
    r = cancel_test_post(comps, external_id="ext-99")
    assert r["ok"] and r["external_id"] == "ext-99"
    db.log("short", 2, "youtube", "test_scheduled", "ext-88 @ 2026-04-01")
    r2 = cancel_test_post(comps, legacy_post_id="ext-88")
    assert r2["ok"] and r2["deleted"] == "ext-88"
    with pytest.raises(TestPublishError):
        cancel_test_post(comps, external_id="never-scheduled")


def test_remote_scan_claim_no_platform_write(tmp_path):
    """_claim must not write legacy_post_id."""
    from orchestrator.remote_scan.service import RemoteScanService

    cfg = _cfg()
    db = Database(tmp_path / "rs.sqlite")
    db.execute(
        "INSERT INTO shorts (source, folder_path, title_text, video_path, created_at) "
        "VALUES ('s', '/r1', 'R', '/r1.mp4', ?)",
        (datetime(2026, 4, 1, tzinfo=UTC).isoformat(),),
    )
    sid = db.fetchone("SELECT id FROM shorts WHERE folder_path='/r1'")["id"]
    svc = RemoteScanService(db, cfg, module_registry=None)
    svc._claim("short", sid, "youtube", "yt-abc", "https://youtu.be/yt-abc")
    row = db.fetchone(
        "SELECT external_id, legacy_post_id, source FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=? AND platform='youtube'",
        (sid,),
    )
    assert row["external_id"] == "yt-abc"
    assert row["source"] == "remote_scan"
    assert not row["legacy_post_id"]


def test_no_runtime_platform_nonnull_assign():
    """Static: no legacy_post_id=? / legacy_scheduled_for=? in runtime (non-NULL)."""
    src = ROOT / "src" / "orchestrator"
    bad = []
    for path in src.rglob("*.py"):
        if path.name == "db.py":
            continue
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if "legacy_post_id=?" in line or "legacy_scheduled_for=?" in line:
                if "NULL" in line:
                    continue
                bad.append(f"{path.relative_to(ROOT)}:{i}:{line.strip()}")
    assert not bad, "runtime non-null platform writes:\n" + "\n".join(bad)


def test_resolve_engine_rejects_platform():
    from orchestrator.platforms import resolve_engine

    with pytest.raises(ValueError):
        resolve_engine("legacy_transport")
