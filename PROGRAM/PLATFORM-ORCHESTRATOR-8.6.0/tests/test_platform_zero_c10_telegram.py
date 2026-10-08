"""platform-zero COMMIT 10: Telegram module inventory unsupported; link-mode."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.platforms.base import NotSupported  # noqa: E402
from orchestrator.platforms.manifest import load_manifest  # noqa: E402
from orchestrator.platforms.telegram.module import TelegramModule  # noqa: E402


def test_telegram_manifest_scan_unsupported():
    m = load_manifest(ROOT / "src/orchestrator/platforms/telegram/manifest.yaml")
    assert m.capabilities.get("scan_mode") == "unsupported"
    assert m.capabilities.get("schedule_owner") == "orchestrator"
    assert m.capabilities.get("list_uploads") is False


def test_telegram_list_remote_not_supported():
    mod = TelegramModule(token="x:y", chat_id="@test")
    with pytest.raises(NotSupported):
        mod.list_remote_items(kinds={"published"})


