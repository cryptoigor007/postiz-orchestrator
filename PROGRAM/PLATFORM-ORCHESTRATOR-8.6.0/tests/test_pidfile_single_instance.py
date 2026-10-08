"""Z01 / REL-02 pidfile single-instance."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from orchestrator.pidfile import acquire_pidfile


def test_pidfile_acquire_and_block(tmp_path: Path):
    pf = tmp_path / "orch.pid"
    acquire_pidfile(pf)
    assert pf.exists()
    assert pf.read_text().strip().isdigit()
    # second acquire must exit
    with pytest.raises(SystemExit) as ei:
        acquire_pidfile(pf)
    assert ei.value.code == 1
