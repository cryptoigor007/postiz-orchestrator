from __future__ import annotations

import logging
import threading
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator


@dataclass
class Circuit:
    failures: int = 0
    opened_at: float | None = None
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_error: str = ""
    half_open_until: float | None = None
    last_state: str = "unknown"


logger = logging.getLogger(__name__)

class ProviderSupervisor:
    """Provider/account isolation, circuit breaker, execution queues and probes."""

    def __init__(self, db: Any = None, *, failure_threshold: int = 5, cooldown_sec: int = 300,
                 probe_lease_sec: int = 30, metrics: Any = None, alert_callback: Callable[[dict[str, Any]], None] | None = None):
        self.db = db
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_sec = max(1, int(cooldown_sec))
        self.probe_lease_sec = max(1, int(probe_lease_sec))
        self.metrics = metrics
        self.alert_callback = alert_callback
        self._circuits: dict[str, Circuit] = {}
        self._loaded: set[str] = set()
        self._queue_locks: dict[str, threading.Lock] = {}
        self._alerted: dict[str, float] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(provider: str, account_id: str = "") -> str:
        return f"{provider.strip().lower()}::{account_id.strip()}"

    def _load(self, provider: str, account_id: str = "") -> Circuit:
        key = self._key(provider, account_id)
        if key in self._loaded:
            return self._circuits.setdefault(key, Circuit())
        self._loaded.add(key)
        c = self._circuits.setdefault(key, Circuit())
        if self.db is None:
            return c
        try:
            row = self.db.fetchone(
                "SELECT state, consecutive_failures, last_success_at, last_failure_at, last_error FROM provider_health WHERE platform=? AND account_id=?",
                (provider.strip().lower(), account_id or ""),
            )
            if row:
                c.failures = int(row.get("consecutive_failures") or 0)
                c.last_success_at = row.get("last_success_at")
                c.last_failure_at = row.get("last_failure_at")
                c.last_error = str(row.get("last_error") or "")
                state = str(row.get("state") or "unknown")
                if state == "open":
                    c.opened_at = c.last_failure_at or time.time()
                elif state == "half_open":
                    c.opened_at = c.last_failure_at or time.time()
                    c.half_open_until = time.time() + self.probe_lease_sec
        except Exception:
            logging.getLogger(__name__).debug("provider health load failed", exc_info=True)
        return c

    @contextmanager
    def queue(self, provider: str, account_id: str = "", *, timeout: float | None = None) -> Iterator[bool]:
        """Serialize provider operations per account while keeping accounts isolated."""
        key = self._key(provider, account_id)
        with self._lock:
            lock = self._queue_locks.setdefault(key, threading.Lock())
        acquired = lock.acquire(timeout=timeout) if timeout is not None else lock.acquire()
        try:
            yield acquired
        finally:
            if acquired:
                lock.release()

    def run_probe(self, provider: str, account_id: str, probe: Callable[[], Any]) -> bool:
        """Run one safe auth/status probe; half-open only. No publish is performed here."""
        if not self.allow(provider, account_id):
            return False
        with self.queue(provider, account_id, timeout=0) as acquired:
            if not acquired:
                return False
            try:
                probe()
            except Exception as exc:
                self.record_failure(provider, account_id, str(exc))
                return False
            self.record_success(provider, account_id)
            return True

    def record_success(self, provider: str, account_id: str = "") -> None:
        with self._lock:
            c = self._load(provider, account_id)
            c.failures = 0
            c.opened_at = None
            c.half_open_until = None
            c.last_success_at = time.time()
            c.last_error = ""
            c.last_state = "healthy"
            self._persist(provider, account_id, c, "healthy")
            self._metric("provider_success", provider, account_id)

    def record_failure(self, provider: str, account_id: str = "", error: str = "") -> None:
        with self._lock:
            c = self._load(provider, account_id)
            now = time.time()
            c.failures += 1
            c.last_failure_at = now
            c.last_error = str(error)[:500]
            if c.half_open_until is not None or c.failures >= self.failure_threshold:
                c.opened_at = now
                c.half_open_until = None
            state = "open" if c.opened_at is not None else "degraded"
            prev = c.last_state
            c.last_state = state
            self._persist(provider, account_id, c, state)
            self._metric("provider_failure", provider, account_id)
            if state in {"open", "degraded"} and state != prev:
                self._emit_alert(provider, account_id, state, c.last_error)

    def allow(self, provider: str, account_id: str = "") -> bool:
        with self._lock:
            c = self._load(provider, account_id)
            if c.opened_at is None:
                return True
            now = time.time()
            if now - c.opened_at < self.cooldown_sec:
                return False
            if c.half_open_until is not None and c.half_open_until > now:
                return False
            c.half_open_until = now + self.probe_lease_sec
            self._persist(provider, account_id, c, "half_open")
            return True

    def reset(self, provider: str, account_id: str = "") -> None:
        with self._lock:
            c = self._load(provider, account_id)
            c.failures = 0
            c.opened_at = None
            c.half_open_until = None
            c.last_error = ""
            c.last_state = "healthy"
            self._persist(provider, account_id, c, "healthy")

    def state(self, provider: str, account_id: str = "") -> str:
        with self._lock:
            c = self._load(provider, account_id)
            if c.opened_at is not None:
                now = time.time()
                if now - c.opened_at < self.cooldown_sec:
                    return "open"
                if c.half_open_until is not None and c.half_open_until > now:
                    return "half_open"
                return "degraded"
            if c.failures:
                return "degraded"
            return "healthy"

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            out: dict[str, dict[str, Any]] = {}
            if self.db is not None:
                try:
                    rows = self.db.fetchall("SELECT * FROM provider_health")
                    for row in rows:
                        self._load(str(row.get("platform") or ""), str(row.get("account_id") or ""))
                except Exception:
                    logging.getLogger(__name__).debug("provider health snapshot load failed", exc_info=True)
            for key, c in self._circuits.items():
                provider, _, account = key.partition("::")
                out[key] = {
                    "provider": provider, "account_id": account, "state": self.state(provider, account),
                    "consecutive_failures": c.failures, "last_success_at": c.last_success_at,
                    "last_failure_at": c.last_failure_at, "last_error": c.last_error,
                }
            return out

    def _metric(self, name: str, provider: str, account_id: str) -> None:
        if self.metrics is None:
            return
        try:
            self.metrics.incr(name)
            self.metrics.incr(f"{name}.{provider}.{account_id or '_'}")
        except Exception:
            logging.getLogger(__name__).debug("provider metrics increment failed", exc_info=True)

    def _emit_alert(self, provider: str, account_id: str, state: str, error: str) -> None:
        if self.alert_callback is None:
            return
        key = self._key(provider, account_id)
        now = time.time()
        if now - self._alerted.get(key, 0) < min(self.cooldown_sec, 300):
            return
        self._alerted[key] = now
        try:
            self.alert_callback({"provider": provider, "account_id": account_id, "state": state, "error": error})
        except Exception:
            logging.getLogger(__name__).debug("provider alert callback failed", exc_info=True)

    def _persist(self, provider: str, account_id: str, c: Circuit, state: str) -> None:
        if self.db is None:
            return
        try:
            self.db.execute(
                """INSERT INTO provider_health
                    (platform, account_id, state, consecutive_failures, last_success_at,
                     last_failure_at, last_error, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(platform, account_id) DO UPDATE SET
                    state=excluded.state,
                    consecutive_failures=excluded.consecutive_failures,
                    last_success_at=excluded.last_success_at,
                    last_failure_at=excluded.last_failure_at,
                    last_error=excluded.last_error,
                    updated_at=excluded.updated_at""",
                (provider.strip().lower(), account_id or "", state, c.failures,
                 c.last_success_at, c.last_failure_at, c.last_error, time.time()),
            )
        except Exception:
            logger.exception("provider health persistence failed (%s/%s)", provider, account_id or "")
