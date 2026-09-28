from datetime import UTC, date, datetime

from orchestrator.daily_ahead import AheadItem, plan_horizon, run_daily_ahead
from orchestrator.platforms.base import UploadResult


def test_plan_horizon():
    d = plan_horizon(date(2030, 1, 1), days=2)
    assert d == [date(2030, 1, 1), date(2030, 1, 2)]


def test_daily_ahead_dry_skip_existing():
    class Y:
        def upload(self, media, meta, when=None):
            return UploadResult(external_id="x", state="scheduled")

    items = [
        AheadItem(path="/a.mp4", title="a", slot=datetime(2030, 1, 1, tzinfo=UTC), external_id="yt:1"),
        AheadItem(path="/b.mp4", title="b", slot=datetime(2030, 1, 2, tzinfo=UTC)),
    ]
    r = run_daily_ahead(items, Y(), dry_run=True)
    assert r.skipped == 1
    assert r.uploaded == 1


def test_daily_ahead_noop_without_module():
    r = run_daily_ahead([], None)
    assert r.errors

def test_daily_ahead_cfg_defaults():
    from pathlib import Path

    from orchestrator.config import DailyAheadCfg, load_config
    da = DailyAheadCfg()
    assert da.enabled is False and da.hour == 9 and da.dry_run is True
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    assert cfg.daily_ahead.enabled is False

def test_maybe_daily_ahead_skips_when_already_today():
    from datetime import datetime
    from types import SimpleNamespace

    from orchestrator.runner import Runner
    class FakeRunner(Runner):
        def __init__(self):
            self.cfg = SimpleNamespace(
                daily_ahead=SimpleNamespace(enabled=True, hour=9, minute=0, days=2, dry_run=True),
                timezone="UTC",
            )
            self.comps = {}
            self.dry_run = True
        def _cycle_daily_ahead(self):
            raise AssertionError("should not run")
    today = datetime.now(UTC).date().isoformat()
    assert FakeRunner()._maybe_daily_ahead(today) == today
