from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


def parse_time(s: str) -> time:
    h, m = map(int, s.split(":"))
    return time(h, m)


def get_tz(name: str = "Europe/Moscow") -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def local_to_utc(d: date, t: time, tz_name: str) -> datetime:
    """Interpret wall-clock date+time in tz_name, return UTC datetime."""
    tz = get_tz(tz_name)
    local = datetime.combine(d, t, tzinfo=tz)
    return local.astimezone(UTC)


def daterange_dates(start: date, end: date) -> Iterator[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def thematic_slot_days(
    long_video_date: datetime,
    next_long_date: datetime | None,
    default_time: str = "20:30",
    tz_name: str = "Europe/Moscow",
    horizon_days: int = 7,
) -> list[datetime]:
    """
    All days from long_video_date (inclusive) to the day before next_long_date.
    Times are wall-clock in tz_name, returned as UTC.
    If next_long_date is None, use horizon_days (default 7) from long date.
    """
    if long_video_date.tzinfo is None:
        long_video_date = long_video_date.replace(tzinfo=UTC)
    tz = get_tz(tz_name)
    local_long = long_video_date.astimezone(tz)
    t = parse_time(default_time)

    if next_long_date is None:
        end_day = local_long.date() + timedelta(days=max(0, horizon_days - 1))
        return [
            local_to_utc(d, t, tz_name)
            for d in daterange_dates(local_long.date(), end_day)
        ]

    if next_long_date.tzinfo is None:
        next_long_date = next_long_date.replace(tzinfo=UTC)
    local_next = next_long_date.astimezone(tz)
    end_day = local_next.date() - timedelta(days=1)
    if end_day < local_long.date():
        end_day = local_long.date()

    return [
        local_to_utc(d, t, tz_name)
        for d in daterange_dates(local_long.date(), end_day)
    ]


def next_long_video_dates(
    days: list[str],
    time_str: str,
    from_dt: datetime,
    count: int = 10,
    exception_days: list[str] | None = None,
    tz_name: str = "Europe/Moscow",
) -> list[datetime]:
    """Future long-video times: wall-clock in tz_name, returned UTC."""
    exception_days = set(exception_days or [])
    weekday_set = {DAY_MAP[d.lower()[:3]] for d in days}
    t = parse_time(time_str)
    tz = get_tz(tz_name)

    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=UTC)
    local_from = from_dt.astimezone(tz)

    result: list[datetime] = []
    cur = local_from.date()
    guard = 0
    while len(result) < count and guard < 400:
        guard += 1
        if cur.weekday() in weekday_set and cur.isoformat() not in exception_days:
            dt_utc = local_to_utc(cur, t, tz_name)
            if dt_utc > from_dt:
                result.append(dt_utc)
        cur += timedelta(days=1)
    return result


def apply_jitter(dt: datetime, jitter_seconds: int) -> datetime:
    if jitter_seconds <= 0:
        return dt
    h = int(hashlib.md5(dt.isoformat().encode()).hexdigest()[:8], 16)
    offset = (h % (2 * jitter_seconds + 1)) - jitter_seconds
    return dt + timedelta(seconds=offset)


def thematic_days_set(
    long_video_date: datetime,
    next_long_date: datetime | None,
    tz_name: str = "Europe/Moscow",
) -> set[date]:
    """Local dates that are thematic slots (for blocking standalone)."""
    slots = thematic_slot_days(long_video_date, next_long_date, "12:00", tz_name)
    tz = get_tz(tz_name)
    return {s.astimezone(tz).date() for s in slots}
