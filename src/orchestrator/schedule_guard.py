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


def postiz_source(postiz: Any) -> Callable[[str], list[datetime]]:
    """Времена постов, уже запланированных в Postiz (включая созданные вручную)."""

    def fn(platform: str) -> list[datetime]:
        out: list[datetime] = []
        for p in postiz.list_scheduled(platform):
            dt = _parse(p.scheduled_for)
            if dt:
                out.append(dt)
        return out

    return fn


def n8n_source(engine: Any) -> Callable[[str], list[datetime]]:
    """Времена из n8n-воркфлоу (если движок отдаёт расписание)."""

    def fn(platform: str) -> list[datetime]:
        out: list[datetime] = []
        try:
            items = engine.list_uploads()
        except Exception:
            return out
        for it in items:
            dt = _parse(it.get("scheduled_for") or it.get("date") or it.get("published_at"))
            if dt:
                out.append(dt)
        return out

    return fn


class ScheduleGuard:
    """Проверяет, что наш слот не конфликтует с внешними расписаниями (Postiz, n8n)."""

    def __init__(self, cfg: AppConfig, clock: Clock,
                 sources: list[tuple[str, Callable[[str], list[datetime]]]] | None = None,
                 ttl_sec: int = 300):
        self.cfg = cfg
        self.clock = clock
        self.sources = list(sources or [])
        self.ttl_sec = ttl_sec
        self._cache: dict[tuple[str, str], tuple[float, list[datetime]]] = {}

    def _times(self, name: str, fn: Callable, platform: str) -> list[datetime]:
        key = (name, platform)
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and now - cached[0] < self.ttl_sec:
            return cached[1]
        try:
            times = fn(platform) or []
        except Exception:
            logger.debug("schedule source %s failed", name, exc_info=True)
            times = []
        self._cache[key] = (now, times)
        return times

    def busy(self, platform: str) -> list[datetime]:
        out: list[datetime] = []
        for name, fn in self.sources:
            out.extend(self._times(name, fn, platform))
        return out

    def conflict(self, platform: str, when: datetime) -> str | None:
        if when is None:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        minutes = getattr(self.cfg.safety, "conflict_window_minutes", 0) \
            or self.cfg.safety.min_interval_minutes
        window = timedelta(minutes=minutes)
        for t in self.busy(platform):
            if abs((t - when).total_seconds()) < window.total_seconds():
                return f"schedule_conflict:{t.isoformat()}"
        return None
