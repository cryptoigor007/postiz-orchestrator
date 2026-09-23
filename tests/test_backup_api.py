"""10.1 backup uses Connection.backup API."""
from __future__ import annotations

from pathlib import Path

from orchestrator.backup import run_backup
from orchestrator.config import load_config
from orchestrator.db import Database

ROOT = Path(__file__).resolve().parents[1]


def test_backup_creates_file(tmp_path):
    db = Database(str(tmp_path / "src.sqlite"))
    db.execute(
        "INSERT INTO system_state (key, value, updated_at) VALUES ('t','1','2026-01-01')"
    )
    cfg = load_config(ROOT / "config.yaml")
    cfg.backup.enabled = True
    dest = run_backup(db, cfg, tmp_path / "bak")
    assert dest is not None
    assert dest.exists()
    assert dest.stat().st_size > 0
