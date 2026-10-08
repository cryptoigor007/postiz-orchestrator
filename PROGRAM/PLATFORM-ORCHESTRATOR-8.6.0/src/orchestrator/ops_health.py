from __future__ import annotations

import json
import shutil
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any


class OpsHealth:
    """Operational readiness checks: disk, backups, config and token expiry."""

    def __init__(self, *, db: Any, cfg: Any, token_store: Any = None, backup_dir: str | Path | None = None):
        self.db = db
        self.cfg = cfg
        self.token_store = token_store
        self.backup_dir = Path(backup_dir) if backup_dir else Path(db.path).resolve().parent.parent / "backups"

    def _disk(self) -> dict[str, Any]:
        usage = shutil.disk_usage(Path(self.db.path).resolve().parent)
        min_bytes = int(getattr(getattr(self.cfg, "ops", None), "min_free_disk_mb", 512) or 512) * 1024 * 1024
        return {
            "free_bytes": usage.free,
            "total_bytes": usage.total,
            "min_free_bytes": min_bytes,
            "ok": usage.free >= min_bytes,
        }

    def _backups(self) -> dict[str, Any]:
        files = sorted(self.backup_dir.glob("data_*.sqlite"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        if not files:
            return {"ok": False, "latest": None, "age_sec": None}
        latest = files[0]
        age = max(0.0, time.time() - latest.stat().st_mtime)
        max_age = float(getattr(getattr(self.cfg, "ops", None), "max_backup_age_hours", max(2, int(getattr(self.cfg.backup, "interval_hours", 6) or 6) * 2)) or 12) * 3600
        ok = age <= max_age
        try:
            with closing(sqlite3.connect(latest)) as con:
                check = con.execute("PRAGMA quick_check").fetchone()[0]
            ok = ok and str(check).lower() == "ok"
            quick = str(check)
        except Exception as exc:
            ok = False
            quick = f"error:{exc}"
        return {"ok": ok, "latest": str(latest), "age_sec": age, "quick_check": quick}

    def _tokens(self) -> dict[str, Any]:
        root = Path(getattr(self.token_store, "root", "tokens")) if self.token_store else Path("tokens")
        warn_hours = float(getattr(getattr(self.cfg, "ops", None), "token_expiry_warn_hours", 24) or 24)
        now = time.time()
        expiring = revoked = quarantined = malformed = 0
        for path in root.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("revoked"): revoked += 1
                if data.get("quarantined"): quarantined += 1
                expires = data.get("expires_at")
                if expires is not None and float(expires) <= now + warn_hours * 3600 and not data.get("revoked"):
                    expiring += 1
            except Exception:
                malformed += 1
        return {"expiring_soon": expiring, "revoked": revoked, "quarantined": quarantined, "malformed": malformed}

    def snapshot(self) -> dict[str, Any]:
        disk = self._disk()
        backups = self._backups()
        tokens = self._tokens()
        ready = bool(disk["ok"] and backups["ok"])
        return {
            "config_schema_version": int(getattr(self.cfg, "config_schema_version", 1)),
            "disk": disk,
            "backups": backups,
            "tokens": tokens,
            "ready": ready,
        }
