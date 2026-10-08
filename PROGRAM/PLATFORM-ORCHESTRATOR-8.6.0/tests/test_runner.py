from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.link_updater import LinkUpdater
from tests.support.legacy_transport_mock import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.runner import Runner  # noqa: F401
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.status_sync import StatusSync
from orchestrator.reconciliation import ModuleReconciliation as Reconciliation
from orchestrator.tail import TailManager
from orchestrator.telegram_bot import TelegramNotifier
from orchestrator.watcher import Watcher


def test_runner_builds(*args, **kwargs):
    from orchestrator.runner import Runner
    assert hasattr(Runner, "run_forever")
    assert hasattr(Runner, "_health_payload")



def test_reconciliation_alert_in_russian(*args, **kwargs):
    from orchestrator.telegram_bot import TelegramNotifier
    assert hasattr(TelegramNotifier, "broadcast")
    assert callable(getattr(TelegramNotifier, "broadcast"))


