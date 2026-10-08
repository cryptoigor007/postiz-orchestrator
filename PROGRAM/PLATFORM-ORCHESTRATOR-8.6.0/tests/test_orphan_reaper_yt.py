"""YT-01 orphan reaper unit (no live API)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import importlib.util
from pathlib import Path as _P
_tool = _P(__file__).resolve().parents[1] / 'tools' / 'yt_orphan_reaper.py'
if not _tool.is_file():
    pytest.skip("tools/yt_orphan_reaper.py is absent from this checkout", allow_module_level=True)
_spec = importlib.util.spec_from_file_location(
    'yt_orphan_reaper', _tool)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
reaper_diff, run = _mod.reaper_diff, _mod.run


def test_reaper_diff_logic():
    missing, orphans = reaper_diff({"a", "b"}, {"b", "c"})
    assert missing == {"a"}
    assert orphans == {"c"}


def test_reaper_run_with_mock_list(tmp_path: Path):
    from orchestrator.db import Database
    dbp = tmp_path / "o.sqlite"
    db = Database(str(dbp))
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, external_id) "
        "VALUES ('long_video', 1, 'youtube', 'published', 'vid_a')"
    )
    db.execute(
        "INSERT INTO entity_platform_status "
        "(entity_type, entity_id, platform, status, external_id) "
        "VALUES ('long_video', 2, 'youtube', 'published', 'vid_b')"
    )
    out = run(str(dbp), apply=False, list_remote=lambda: ["vid_b", "vid_c"])
    assert "vid_a" in out["missing"]
    assert "vid_c" in out["orphans"]
    assert out["eps"] == 2


def test_orphan_reaper_cli_help():
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, str(root / "tools" / "yt_orphan_reaper.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=str(root),
    )
    assert r.returncode == 0
