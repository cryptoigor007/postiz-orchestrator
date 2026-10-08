from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.provider_catalog import load_provider_catalog
from orchestrator.platforms import default_registry


def test_provider_catalog_has_no_duplicates_and_all_entries_registered():
    entries = load_provider_catalog()
    ids = [x.id for x in entries]
    assert len(ids) == len(set(ids))
    reg = default_registry()
    missing = [pid for pid in ids if not reg.has(pid)]
    assert missing == []


def test_live_status_and_special_provider_semantics_are_honest():
    entries = {x.id: x for x in load_provider_catalog()}
    assert len(entries) == 42
    assert all(getattr(x, "live_status", "") == "NOT_LIVE" for x in entries.values())
    assert "inbox" in str(entries["tiktok"].publish_semantics).lower()
    assert "manual" in str(entries["tiktok"].publish_semantics).lower()
    assert "unsupported" in str(entries["telegram"].publish_semantics).lower()
    assert "media_host" in str(entries["instagram"].live_requirements).lower()
