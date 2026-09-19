from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.db import Database


def test_upsert_upload_idempotent(tmp_path):
    db = Database(tmp_path / "u.sqlite")
    a = db.upsert_upload(
        engine="direct", platform="youtube", external_id="vid1",
        url="https://y/vid1", title="T", published_at="2026-09-01T10:00:00+00:00",
        origin="manual",
    )
    assert a["match_status"] == "unmatched"
    assert a["id"] > 0

    b = db.upsert_upload(
        engine="direct", platform="youtube", external_id="vid1",
        url="https://y/vid1", title="T2", published_at="2026-09-01T10:00:00+00:00",
        origin="manual",
    )
    assert b["id"] == a["id"]
    assert b["title"] == "T2"
    assert len(db.list_uploads()) == 1


def test_upload_confirm_unique_per_entity(tmp_path):
    db = Database(tmp_path / "u2.sqlite")
    u1 = db.upsert_upload(engine="direct", platform="youtube", external_id="v1",
                          origin="manual")
    u2 = db.upsert_upload(engine="direct", platform="youtube", external_id="v2",
                          origin="manual")
    db.set_upload_match(u1["id"], "long_video", 10, 0.9, "confirmed")
    row = db.get_upload(u1["id"])
    assert row["match_status"] == "confirmed"
    assert row["matched_entity_id"] == 10
    # same entity on same platform -> unique index must reject a second confirmed match
    import sqlite3
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        db.set_upload_match(u2["id"], "long_video", 10, 0.8, "confirmed")


def test_list_uploads_filter(tmp_path):
    db = Database(tmp_path / "u3.sqlite")
    db.upsert_upload(engine="direct", platform="youtube", external_id="a", origin="manual")
    db.upsert_upload(engine="postiz", platform="telegram", external_id="b", origin="postiz")
    assert len(db.list_uploads(platform="youtube")) == 1
    assert len(db.list_uploads()) == 2
