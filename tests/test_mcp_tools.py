from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import mcp_server
import postiz_mcp_server


def test_orchestrator_mcp_tools_complete():
    names = {t[0] for t in mcp_server.TOOLS}
    for n in ("orch_status", "orch_sync", "orch_reconcile", "orch_backup",
              "orch_schedule", "orch_pause_platform", "orch_manual_scan",
              "orch_manual_confirm", "orch_roots", "orch_browse"):
        assert n in names, n


def test_postiz_mcp_tools():
    names = {t[0] for t in postiz_mcp_server.TOOLS}
    assert {"postiz_integrations", "postiz_create", "postiz_posts"} <= names
