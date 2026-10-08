from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from orchestrator.backlog import BacklogManager
from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.telegram_bot import TelegramNotifier, setup_commands
from tests.support.module_test_helpers import make_module_registry

ROOT = Path(__file__).resolve().parents[1]


def test_scheduler_backlog_active_uses_account_scoped_sql_params(tmp_path):
    db = Database(tmp_path / "sched.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    cfg.platforms["youtube"].account_id = "acct-2"
    clock = FakeClock(datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=False,
                    module_registry=make_module_registry(dry_run=True))
    sched = Scheduler(db, cfg, pub, safety, clock)

    db.execute(
        "INSERT INTO platform_queue_account_state(platform,account_id,series_tail_mode,pending_series_end_question) "
        "VALUES('youtube','acct-2',1,0)"
    )
    db.execute(
        "INSERT INTO long_videos(source,folder_path,title_text,created_at) VALUES('videomaker','/series','Series',?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos")['id']
    db.execute(
        "INSERT INTO shorts(source,parent_video_id,folder_path,order_index,video_path,title_text,created_at) "
        "VALUES('videomaker',?,?,?,?,?,?)",
        (vid, '/series/short0', 0, '/series/short0/v.mp4', 'Short 0', clock.now().isoformat()),
    )

    assert sched._backlog_active("youtube") is True


def test_telegram_backlog_commands_require_and_carry_account_scope(tmp_path):
    db = Database(tmp_path / "tg.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    cfg.platforms["youtube"].account_id = ""
    cfg.telegram.allowed_chat_ids = [777]
    clock = FakeClock(datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=True)
    sched = Scheduler(db, cfg, pub, safety, clock)
    mgr = BacklogManager(db, cfg, clock, scheduler=sched)
    tg = TelegramNotifier(cfg, db, clock)
    setup_commands(tg, {"db": db, "cfg": cfg, "safety": safety, "scheduler": sched, "clock": clock, "backlog": mgr})

    for eid, aid in ((101, "acct-1"), (102, "acct-2")):
        db.execute(
            "INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) "
            "VALUES('short',?,'youtube',?,'ready')", (eid, aid),
        )

    chat = 777
    ambiguous = tg.handle_update(chat, "/backlog_wait youtube")
    assert ambiguous and "account_id" in ambiguous

    explicit = tg.handle_update(chat, "/backlog_wait youtube acct-1")
    assert "acct-1" in explicit
    row1 = db.fetchone(
        "SELECT pending_backlog_question,series_tail_mode FROM platform_queue_account_state "
        "WHERE platform='youtube' AND account_id='acct-1'"
    )
    row2 = db.fetchone(
        "SELECT pending_backlog_question,series_tail_mode FROM platform_queue_account_state "
        "WHERE platform='youtube' AND account_id='acct-2'"
    )
    assert row1 and row1['series_tail_mode'] == 0
    assert row2 is None

    markup = tg._backlog_markup("youtube", "acct-2")
    callbacks = [button['callback_data'] for row in markup['inline_keyboard'] for button in row]
    assert callbacks == [
        "backlog_distribute youtube acct-2",
        "backlog_wait youtube acct-2",
        "backlog_skip youtube acct-2",
    ]


def test_backlog_default_and_reminder_are_account_scoped(tmp_path):
    db = Database(tmp_path / "backlog.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    cfg.platforms["youtube"].account_id = "acct-1"
    clock = FakeClock(datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    mgr = BacklogManager(db, cfg, clock)

    mgr.ask("youtube", clock.now() + timedelta(hours=1), account_id="acct-1")
    assert mgr.awaiting("youtube", "acct-1") is True
    # These paths used to reference an undefined local `account_id`.
    assert mgr.should_remind("youtube", clock.now(), "acct-1") is None
    assert mgr.auto_default("youtube", clock.now(), "acct-1") == 0
    assert mgr.missed_default("youtube", clock.now(), "acct-1") == 0


def test_backlog_notifier_receives_account_scope(tmp_path):
    class Notifier:
        def __init__(self):
            self.calls = []

        def ask_backlog(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    db = Database(tmp_path / "backlog-notifier.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    cfg.platforms["youtube"].account_id = "acct-1"
    clock = FakeClock(datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    notifier = Notifier()
    mgr = BacklogManager(db, cfg, clock, notifier=notifier)

    # Seed one account-scoped backlog item so ask() actually notifies.
    db.execute(
        "INSERT INTO long_videos(source,folder_path,title_text,created_at) VALUES('v','/series','Series',?)",
        (clock.now().isoformat(),),
    )
    vid = db.fetchone("SELECT id FROM long_videos")['id']
    db.execute(
        "INSERT INTO shorts(source,parent_video_id,folder_path,order_index,video_path,title_text,created_at) "
        "VALUES('videomaker',?,?,?,?,?,?)",
        (vid, '/series/short0', 0, '/series/short0/v.mp4', 'Short 0', clock.now().isoformat()),
    )
    mgr.ask("youtube", clock.now() + timedelta(hours=1), account_id="acct-1")
    assert notifier.calls and notifier.calls[-1][1]["account_id"] == "acct-1"


def test_publisher_provider_circuit_defers_with_retry_metadata(tmp_path):
    class TwoPhaseSupervisor:
        def __init__(self):
            self.calls = 0

        def allow(self, _platform, _account_id):
            self.calls += 1
            return self.calls == 1

        def queue(self, _platform, _account_id, *, timeout=None):
            raise AssertionError("queue must not be entered when second allow() denies")

    db = Database(tmp_path / "publish.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    cfg.platforms["youtube"].account_id = "acct-1"
    clock = FakeClock(datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    safety = SafetyChecker(db, cfg, clock)
    supervisor = TwoPhaseSupervisor()
    publisher = Publisher(db, cfg, safety, clock, dry_run=False,
                          module_registry=make_module_registry(dry_run=True), supervisor=supervisor)

    out = publisher.publish("short", 9001, "youtube", None, {}, account_id="acct-1")
    assert out is None
    assert supervisor.calls == 2
    row = db.fetchone(
        "SELECT status,last_error,next_retry_at FROM entity_platform_status "
        "WHERE entity_type='short' AND entity_id=9001 AND platform='youtube' AND account_id='acct-1'"
    )
    assert row and row['status'] == 'ready'
    assert row['next_retry_at']
    attempt = db.fetchone(
        "SELECT status,error_code,error_message FROM publish_attempts "
        "WHERE entity_type='short' AND entity_id=9001 AND platform='youtube' AND account_id='acct-1'"
    )
    assert attempt and attempt['status'] == 'deferred' and attempt['error_code'] == 'CIRCUIT_OPEN'


def test_webhook_dead_letter_branch_marks_event_dead(tmp_path):
    from orchestrator.webhook_processor import WebhookEventProcessor

    db = Database(tmp_path / "webhook-dlq.sqlite")
    db.execute(
        "INSERT INTO webhook_events(provider,account_id,event_id,payload_hash,signature_valid,received_at,payload_json) "
        "VALUES('x','acct-1','dead-1','h',1,datetime('now'),'{}')"
    )
    result = WebhookEventProcessor(db, max_attempts=1).run()
    row = db.fetchone("SELECT processing_state,processed_at,last_error FROM webhook_events WHERE event_id='dead-1'")
    assert result.dead == 1 and result.retried == 0
    assert row['processing_state'] == 'dead' and row['processed_at'] is None
    assert row['last_error']


def test_gui_smoke_script_validates_real_jsdom_installation():
    text = (ROOT / 'scripts' / 'ci_gui_smoke.sh').read_text(encoding='utf-8')
    assert '[ ! -f node_modules/jsdom/package.json ]' in text
    assert 'npm ci --silent' in text
