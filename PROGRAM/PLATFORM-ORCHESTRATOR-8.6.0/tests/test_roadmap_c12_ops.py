from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from orchestrator.backup import run_backup, verify_backup
from orchestrator.config import load_config
from orchestrator.config_migrations import CURRENT_CONFIG_SCHEMA_VERSION, migrate_config_dict
from orchestrator.db import Database
from orchestrator.metrics import Metrics
from orchestrator.ops_health import OpsHealth
from orchestrator.token_lifecycle import TokenLifecycleStore

ROOT = Path(__file__).resolve().parents[1]


def test_config_v1_migrates_account_id():
    raw = {"schedules": {}, "platforms": {"x": {"integration_id": "old-account"}}}
    migrated = migrate_config_dict(raw)
    assert migrated["config_schema_version"] == CURRENT_CONFIG_SCHEMA_VERSION
    assert migrated["platforms"]["x"]["account_id"] == "old-account"


def test_metrics_flush_is_atomic_and_secure(tmp_path):
    path = tmp_path / "metrics.json"
    m = Metrics(path)
    m.incr("cycles", 2)
    m.flush()
    assert json.loads(path.read_text())["cycles"] == 2
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".metrics.json.*"))


def test_backup_verify_quick_check(tmp_path):
    db = Database(tmp_path / "source.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    dest = run_backup(db, cfg, tmp_path / "backup")
    assert dest is not None
    result = verify_backup(dest)
    assert result["ok"] is True
    assert result["quick_check"] == "ok"


def test_ops_health_reports_disk_backup_and_token_expiry(tmp_path):
    db = Database(tmp_path / "source.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    cfg.ops.min_free_disk_mb = 1
    cfg.ops.max_backup_age_hours = 24
    cfg.ops.token_expiry_warn_hours = 24
    backup_dir = tmp_path / "backup"
    dest = run_backup(db, cfg, backup_dir)
    assert dest is not None
    tokens = TokenLifecycleStore(tmp_path / "tokens", db=db)
    tokens.rotate("youtube", "acct", access_token="a", expires_at=__import__("time").time() + 60)
    health = OpsHealth(db=db, cfg=cfg, token_store=tokens, backup_dir=backup_dir).snapshot()
    assert health["disk"]["ok"] is True
    assert health["backups"]["ok"] is True
    assert health["tokens"]["expiring_soon"] == 1
    assert health["ready"] is True
