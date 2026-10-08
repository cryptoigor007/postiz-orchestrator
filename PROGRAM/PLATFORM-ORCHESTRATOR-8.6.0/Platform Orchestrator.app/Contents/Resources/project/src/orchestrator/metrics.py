from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Metrics:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.data: dict[str, Any] = {
            "started_at": time.time(),
            "cycles": 0,
            "scheduled_long": 0,
            "scheduled_short": 0,
            "sync_updates": 0,
            "errors": 0,
            "last_cycle_at": None,
            "last_error": None,
        }
        # рестарт не должен терять счётчики: подхватываем прошлый файл (новые значения — поверх)
        if self.path and self.path.is_file():
            try:
                prev = json.loads(self.path.read_text())
                if isinstance(prev, dict):
                    for k, v in prev.items():
                        if k in ("started_at", "last_cycle_at", "last_error"):
                            continue
                        self.data[k] = v
            except Exception:
                logger.debug("metrics load failed (start fresh)", exc_info=True)

    def incr(self, key: str, n: int = 1) -> None:
        self.data[key] = int(self.data.get(key) or 0) + n

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def tick_cycle(self) -> None:
        self.incr("cycles")
        self.data["last_cycle_at"] = time.time()
        self.flush()

    def flush(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self.data, ensure_ascii=False, indent=2)
            fd, tmp = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent))
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, self.path)
            finally:
                try:
                    os.unlink(tmp)
                except OSError as exc:
                    logger.debug("metrics temp cleanup failed: %s", type(exc).__name__)
        except Exception:
            logger.debug("metrics flush failed", exc_info=True)

    def snapshot(self) -> dict[str, Any]:
        return dict(self.data)


def sanitize_metrics(data: dict) -> dict:
    """S19: strip secrets/tokens from metrics payload before exposure."""
    if not isinstance(data, dict):
        return {}
    banned = ("token", "secret", "password", "api_key", "authorization", "cookie")
    out = {}
    for k, v in data.items():
        kl = str(k).lower()
        if any(b in kl for b in banned):
            continue
        if isinstance(v, dict):
            out[k] = sanitize_metrics(v)
        else:
            out[k] = v
    return out
