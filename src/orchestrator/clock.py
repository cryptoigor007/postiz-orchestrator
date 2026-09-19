from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return current UTC datetime."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock:
    def __init__(self, start: datetime | None = None):
        self._now = start or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def set(self, dt: datetime) -> None:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        self._now = dt

    def advance(self, **kwargs) -> None:
        from datetime import timedelta
        self._now += timedelta(**kwargs)
