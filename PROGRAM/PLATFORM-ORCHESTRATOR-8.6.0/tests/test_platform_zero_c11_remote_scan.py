"""platform-zero COMMIT 11: RemoteScan match one-candidate rule + project isolation."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.remote_scan.service import match_candidates  # noqa: E402


def test_auto_claim_one_candidate():
    remote = {"title": "Hello World Video", "published_at": "2026-03-10", "duration_sec": 60}
    entities = [
        {"entity_type": "short", "entity_id": 1, "title": "Hello World Video", "published_at": "2026-03-10", "duration_sec": 60},
    ]
    decision, ent, score, _ = match_candidates(remote, entities, auto_min=0.5, review_min=0.3)
    assert decision == "auto_claimed"
    assert ent["entity_id"] == 1
    assert score >= 0.5


def test_two_candidates_pending_review():
    remote = {"title": "Same Title Clip", "published_at": "2026-03-10", "duration_sec": 30}
    entities = [
        {"entity_type": "short", "entity_id": 1, "title": "Same Title Clip", "published_at": "2026-03-10", "duration_sec": 30},
        {"entity_type": "short", "entity_id": 2, "title": "Same Title Clip", "published_at": "2026-03-10", "duration_sec": 30},
    ]
    decision, ent, score, _ = match_candidates(remote, entities, auto_min=0.5, review_min=0.3)
    assert decision == "pending_review"
    assert score >= 0.5


def test_no_match_ignored():
    remote = {"title": "xyzzy unique", "published_at": "2020-01-01", "duration_sec": 1}
    entities = [
        {"entity_type": "short", "entity_id": 9, "title": "totally different", "published_at": "2026-12-31", "duration_sec": 999},
    ]
    decision, ent, score, _ = match_candidates(remote, entities, auto_min=0.9, review_min=0.8)
    assert decision == "ignored"
    assert ent is None
