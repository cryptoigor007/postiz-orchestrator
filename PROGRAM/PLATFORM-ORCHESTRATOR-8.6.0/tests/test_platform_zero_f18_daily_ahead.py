
"""F18 daily_ahead module-only + two-bucket quota."""
from __future__ import annotations
import sys
from datetime import UTC, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from orchestrator.daily_ahead import AheadItem, QuotaBuckets, run_daily_ahead_with_quota

class _YT:
    def upload(self, media, meta, when=None):
        return type("U", (), {"external_id": "u1"})()

def test_quota_blocks():
    q = QuotaBuckets(upload_bucket=2, used_upload=0)
    items = [
        AheadItem(path=f"/v{i}.mp4", title=f"t{i}", slot=datetime(2026, 5, 2, 16, tzinfo=UTC))
        for i in range(5)
    ]
    r = run_daily_ahead_with_quota(items, _YT(), q, dry_run=True)
    assert r.uploaded == 2
    assert any("quota" in e for e in (r.errors or []))

def test_idempotent_skip():
    items = [AheadItem(path="/a.mp4", title="t", slot=datetime(2026, 5, 2, 16, tzinfo=UTC), external_id="already")]
    r = run_daily_ahead_with_quota(items, _YT(), dry_run=True)
    assert r.skipped == 1
    assert r.uploaded == 0

def test_posts_per_day_cap():
    items = [
        AheadItem(path=f"/v{i}.mp4", title=f"t{i}", slot=datetime(2026, 5, 2, 16, tzinfo=UTC))
        for i in range(5)
    ]
    r = run_daily_ahead_with_quota(items, _YT(), dry_run=True, posts_per_day=1)
    assert r.uploaded == 1
    assert r.skipped == 4
