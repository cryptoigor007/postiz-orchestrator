from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from .clock import Clock
from .config import AppConfig

logger = logging.getLogger(__name__)


def _parse(ts: Any) -> datetime | None:
    if not ts:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except Exception:
        return None


def eps_source(db: Any) -> Callable[[str, str], list[datetime]]:
    """Busy times from EPS (scheduled / scheduled_platform) — primary C8 source."""

    def fn(platform: str, account_id: str = "") -> list[datetime]:
        out: list[datetime] = []
        try:
            rows = db.fetchall(
                """
                SELECT scheduled_for AS scheduled_for
                FROM entity_platform_status
                WHERE platform=?
                AND (?='' OR account_id=?)
                AND status IN (
                    'scheduled', 'scheduled_platform', 'publishing', 'updating',
                    'uploaded_inbox', 'waiting_manual_publish'
                )
                AND scheduled_for IS NOT NULL
                """,
                (platform, account_id or "", account_id or ""),
            )
        except Exception:
            return out
        for r in rows or []:
            dt = _parse(r.get("scheduled_for"))
            if dt:
                out.append(dt)
        return out

    return fn



class ScheduleGuard:
    """Check slot does not conflict with EPS (+ optional external sources)."""

    def __init__(
        self,
        cfg: AppConfig,
        clock: Clock,
        sources: list[tuple[str, Callable[..., list[datetime]]]] | None = None,
        ttl_sec: int = 120,
    ):
        self.cfg = cfg
        self.clock = clock
        self.sources = list(sources or [])
        self.ttl_sec = ttl_sec
        self._cache: dict[tuple[str, str, str], tuple[float, list[datetime]]] = {}

    def invalidate(self) -> None:
        self._cache.clear()

    def _times(self, name: str, fn: Callable, platform: str, account_id: str = "") -> list[datetime]:
        key = (name, platform, account_id or "")
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and now - cached[0] < self.ttl_sec:
            return cached[1]
        try:
            try:
                times = fn(platform, account_id or "") or []
            except TypeError:
                # Legacy/custom sources still accept only platform.
                times = fn(platform) or []
        except Exception:
            logger.debug("schedule source %s failed", name, exc_info=True)
            times = []
        self._cache[key] = (now, times)
        return times

    def busy(self, platform: str, account_id: str = "") -> list[datetime]:
        out: list[datetime] = []
        for name, fn in self.sources:
            out.extend(self._times(name, fn, platform, account_id))
        return out

    def conflict(self, platform: str, when: datetime, account_id: str = "") -> str | None:
        if when is None:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        minutes = getattr(self.cfg.safety, "conflict_window_minutes", 0) \
            or self.cfg.safety.min_interval_minutes
        window = timedelta(minutes=minutes)
        for t in self.busy(platform, account_id):
            if abs((t - when).total_seconds()) < window.total_seconds():
                return f"schedule_conflict:{t.isoformat()}"
        return None
