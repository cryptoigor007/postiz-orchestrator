from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from tests.support.module_test_helpers import make_module_registry


def _scheduler(tmp_path, account_id):
    db = Database(tmp_path / f"sched-{account_id}.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.ci.yaml")
    cfg.platforms["youtube"].account_id = account_id
    cfg.engines = dict(getattr(cfg, "engines", {}) or {})
    cfg.engines["youtube"] = "module:youtube"
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=False, module_registry=make_module_registry(dry_run=True))
    return db, cfg, clock, Scheduler(db, cfg, pub, safety, clock)


def test_scheduler_queue_state_is_account_scoped(tmp_path):
    db, cfg, clock, sched = _scheduler(tmp_path, "a2")
    db.execute("INSERT INTO platform_queue_account_state(platform,account_id,series_tail_mode,pending_series_end_question) VALUES('youtube','a1',1,1)")
    db.execute("INSERT INTO platform_queue_account_state(platform,account_id,series_tail_mode,pending_series_end_question) VALUES('youtube','a2',0,0)")
    state = sched._queue_state("youtube")
    assert state["series_tail_mode"] == 0
    assert state["pending_series_end_question"] == 0
    assert sched._backlog_active("youtube") is False


def test_scheduler_legacy_queue_state_only_fallbacks_for_single_account(tmp_path):
    db, cfg, clock, sched = _scheduler(tmp_path, "a1")
    db.execute("INSERT INTO platform_queue_state(platform,series_tail_mode,pending_series_end_question) VALUES('youtube',1,1)")
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES('long_video',1,'youtube','a1','ready')")
    assert sched._queue_state("youtube")["series_tail_mode"] == 1
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES('long_video',2,'youtube','a2','ready')")
    assert sched._queue_state("youtube") is None


def test_thematic_parent_is_account_scoped(tmp_path):
    db, cfg, clock, sched = _scheduler(tmp_path, "a2")
    now = clock.now().isoformat()
    db.execute("INSERT INTO long_videos(source,folder_path,title_text,created_at) VALUES('videomaker','/same','Same',?)", (now,))
    db.execute("INSERT INTO long_videos(source,folder_path,title_text,created_at) VALUES('videomaker','/other','Other',?)", (now,))
    rows = db.fetchall("SELECT id FROM long_videos ORDER BY id")
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,release_url,published_at) VALUES('long_video',?,'youtube','a1','published','https://a1','2026-03-09T10:00:00+00:00')", (rows[0]['id'],))
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,release_url,published_at) VALUES('long_video',?,'youtube','a2','published','https://a2','2026-03-09T10:00:00+00:00')", (rows[1]['id'],))
    # a2 must not see a1's entity as its parent release record.
    parent = db.fetchone("SELECT * FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=? AND platform='youtube' AND account_id='a2'", (rows[1]['id'],))
    assert parent["release_url"] == "https://a2"
