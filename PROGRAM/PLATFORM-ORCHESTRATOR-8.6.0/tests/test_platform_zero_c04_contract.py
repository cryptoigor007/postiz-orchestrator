"""platform-zero COMMIT 4: RemoteItem/Page, QuotaSnapshot, list_remote_items contract."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.platforms.base import (  # noqa: E402
    NotSupported,
    PlatformModule,
    QuotaSnapshot,
    RemoteItem,
    RemotePage,
)
from orchestrator.platforms.manifest import (  # noqa: E402
    BOOL_CAPABILITIES,
    ENUM_CAPABILITIES,
    ModuleManifest,
)


def test_remote_item_defaults():
    it = RemoteItem(platform="youtube", external_id="vid1")
    assert it.status == "published"
    assert it.privacy == "unknown"
    assert it.raw == {}


def test_remote_page_and_quota():
    page = RemotePage(items=[], partial=True, notes=["api incomplete"])
    assert page.partial
    q = QuotaSnapshot(unit="api_units", remaining=100, limit=10000)
    assert q.remaining == 100
    q2 = QuotaSnapshot(buckets={"upload": {"limit": 100, "cost": 1}})
    assert "upload" in q2.buckets


def test_base_list_remote_raises_not_supported():
    class _M(PlatformModule):
        def auth_status(self):
            from orchestrator.platforms.base import AuthStatus
            return AuthStatus(ok=False)

    m = _M()
    with pytest.raises(NotSupported):
        m.list_remote_items(kinds={"published"})
    with pytest.raises(NotSupported):
        m.get_quota()
    with pytest.raises(NotSupported):
        m.clear_schedule("x")
    with pytest.raises(NotSupported):
        m.cancel("x")


def test_manifest_allows_new_caps():
    assert "list_uploads" in BOOL_CAPABILITIES
    assert "list_scheduled" in BOOL_CAPABILITIES
    assert "list_private" in BOOL_CAPABILITIES
    assert "scan_mode" in ENUM_CAPABILITIES
    assert "schedule_owner" in ENUM_CAPABILITIES


def test_manifest_scan_mode_validation():
    data = {
        "id": "youtube",
        "name": "YouTube",
        "api_version": "v3",
        "module_version": "2.1.1",
        "core_min": "0.1.0",
        "auth": {"method": "oauth2"},
        "capabilities": {
            "publish": True,
            "list_uploads": True,
            "list_scheduled": True,
            "list_private": True,
            "scan_mode": "auto",
            "schedule_owner": "platform",
            "claims_check": "manual",
        },
        "limits": {},
        "media": {},
        "statuses": {},
        "docs": "MODULE_YOUTUBE.txt",
    }
    m = ModuleManifest.from_dict(data)
    assert m.capabilities["scan_mode"] == "auto"
