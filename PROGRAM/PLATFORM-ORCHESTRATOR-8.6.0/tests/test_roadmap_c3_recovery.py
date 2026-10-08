from __future__ import annotations

from dataclasses import dataclass

from orchestrator.db import Database
from orchestrator.platforms.base import AuthStatus, PublishStatus, RemoteItem, RemotePage
from orchestrator.publish_recovery import PublishAttemptRecovery


class Mod:
    def auth_status(self):
        return AuthStatus(ok=True)
    def get_status(self, external_id):
        return PublishStatus(state="published", url=f"https://x/{external_id}")
    def list_remote_items(self, **kwargs):
        return RemotePage(items=[RemoteItem(platform="fake", external_id="r1", title="Hello", status="published", url="https://x/r1")])


class Registry:
    def has(self, mid): return mid == "fake"
    def create(self, mid, **deps): return Mod()


def test_recovery_repairs_by_known_remote_id(tmp_path):
    db = Database(tmp_path / "r.sqlite")
    db.execute("INSERT INTO long_videos(id,source,folder_path,title_text,created_at) VALUES(1,'x','/x','Hello','now')")
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status,external_id) VALUES('long_video',1,'fake','a','publishing','r1')")
    db.execute("INSERT INTO publish_attempts(id,entity_type,entity_id,platform,account_id,idempotency_key,status,started_at) VALUES('a1','long_video',1,'fake','a','k','started','now')")
    rec = PublishAttemptRecovery(db, Registry())
    result = rec.run()
    assert result.repaired == 1
    assert db.fetchone("SELECT status, remote_object_id FROM publish_attempts WHERE id='a1'") == {"status":"published","remote_object_id":"r1"}


def test_recovery_repairs_unique_inventory_match(tmp_path):
    db = Database(tmp_path / "r2.sqlite")
    db.execute("INSERT INTO long_videos(id,source,folder_path,title_text,created_at) VALUES(1,'x','/x','Hello','now')")
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES('long_video',1,'fake','a','publishing')")
    db.execute("INSERT INTO publish_attempts(id,entity_type,entity_id,platform,account_id,idempotency_key,status,started_at) VALUES('a1','long_video',1,'fake','a','k','unknown','now')")
    result = PublishAttemptRecovery(db, Registry()).run()
    assert result.repaired == 1
    assert db.fetchone("SELECT remote_object_id FROM publish_attempts WHERE id='a1'")["remote_object_id"] == "r1"
    assert db.fetchone("SELECT external_id FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=1 AND platform='fake' AND account_id='a'")["external_id"] == "r1"


def test_recovery_inventory_error_is_distinguished_from_empty_inventory(tmp_path):
    from orchestrator.db import Database
    from orchestrator.publish_recovery import PublishAttemptRecovery

    db = Database(tmp_path / 'invfail.sqlite')
    db.ensure_platform_states(['fake'])
    db.execute("INSERT INTO long_videos(source,folder_path,title,wide_path,created_at) VALUES('s','/g','Title','/g/a.mp4',datetime('now'))")
    vid = db.fetchone("SELECT id FROM long_videos")['id']
    db.execute("INSERT INTO entity_platform_status(entity_type,entity_id,platform,account_id,status) VALUES('long_video',?,'fake','acct','publishing')", (vid,))
    db.execute("INSERT INTO publish_attempts(id,entity_type,entity_id,platform,account_id,idempotency_key,status,started_at) VALUES('inv1','long_video',?,'fake','acct','k','unknown',datetime('now'))", (vid,))
    aid = 'inv1'

    class Mod:
        def list_remote_items(self, limit=50):
            raise RuntimeError('remote down')
    class Registry:
        def has(self, platform): return True
        def create(self, *args, **kwargs): return Mod()

    res = PublishAttemptRecovery(db, Registry()).run()
    row = db.fetchone("SELECT status,error_code FROM publish_attempts WHERE id=?", (aid,))
    assert res.repaired == 0 and res.failed == 0
    assert row['status'] == 'unknown'
    assert row['error_code'] == 'REMOTE_INVENTORY_UNAVAILABLE'
