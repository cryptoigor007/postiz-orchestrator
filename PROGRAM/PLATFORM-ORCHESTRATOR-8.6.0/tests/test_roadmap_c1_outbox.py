from __future__ import annotations

from orchestrator.db import Database
from orchestrator.outbox import Outbox


def test_domain_and_outbox_commit_together(tmp_path):
    db = Database(tmp_path / "c1.sqlite")
    outbox = Outbox(db)
    with db.transaction() as conn:
        conn.execute("INSERT INTO system_state(key,value,updated_at) VALUES('c1','ok','now')")
        outbox.enqueue_in_transaction(conn, "c1.done", "test", "1", {"ok": True})
    assert db.get_setting("c1") == "ok"
    assert db.fetchone("SELECT event_type FROM outbox_events WHERE event_type='c1.done'") is not None


def test_domain_and_outbox_roll_back_together(tmp_path):
    db = Database(tmp_path / "c1_rollback.sqlite")
    outbox = Outbox(db)
    try:
        with db.transaction() as conn:
            conn.execute("INSERT INTO system_state(key,value,updated_at) VALUES('c1','bad','now')")
            outbox.enqueue_in_transaction(conn, "c1.fail", "test", "2", {"ok": False})
            raise RuntimeError("inject rollback")
    except RuntimeError:
        pass
    assert db.get_setting("c1") is None
    assert db.fetchone("SELECT id FROM outbox_events WHERE event_type='c1.fail'") is None
