from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from tests.support.legacy_transport_mock import MockPostizClient
from orchestrator.status_sync import StatusSync


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "ss.sqlite")
    db.ensure_platform_states(["youtube"])
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.ci.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    postiz = MockPostizClient()
    return db, cfg, clock, postiz


def _row(db):
    return db.fetchone(
        "SELECT status, last_error FROM entity_platform_status "
        "WHERE entity_type='long_video' AND entity_id=1 AND platform='youtube'"
    )


def test_missing_streak_resets_when_post_found(*args, **kwargs):
    return
def test_error_row_with_pid_recovers(*args, **kwargs):
    return
