"""Single-instance guard via pidfile + fcntl.flock (Linux).

Z01 / REL-02: second process exits non-zero and logs.
"""
from __future__ import annotations

import atexit
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_lock_fh = None


def acquire_pidfile(path: str | Path) -> None:
    """Acquire exclusive lock on pidfile. Raises SystemExit(1) if held."""
    global _lock_fh
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fh = open(p, "a+", encoding="utf-8")
    try:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.seek(0)
        old = (fh.read() or "").strip()
        logger.error(
            "another orchestrator instance holds pidfile %s (pid=%s); exit",
            p,
            old or "?",
        )
        fh.close()
        raise SystemExit(1) from None
    except ImportError:
        # non-Linux fallback: best-effort write
        logger.warning("fcntl unavailable — pidfile without flock")
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    _lock_fh = fh

    def _release() -> None:
        global _lock_fh
        try:
            if _lock_fh is not None:
                try:
                    import fcntl
                    fcntl.flock(_lock_fh.fileno(), fcntl.LOCK_UN)
                except Exception as exc:
                    logger.debug("pidfile flock unlock failed: %s", type(exc).__name__)
                _lock_fh.close()
                _lock_fh = None
        except Exception as exc:
            logger.debug("pidfile release cleanup failed: %s", type(exc).__name__)

    atexit.register(_release)


def pidfile_path_from_env(default: str = "data/orchestrator.pid") -> str:
    return os.getenv("ORCH_PIDFILE", default)
