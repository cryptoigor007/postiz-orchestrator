from __future__ import annotations
from datetime import datetime, timedelta, time, timezone, date
from typing import Iterator
from zoneinfo import ZoneInfo
import hashlib

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
    return local.astimezone(timezone.utc)


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
) -> list[datetime]:
    """
    All days from long_video_date (inclusive) to the day before next_long_date.
    Times are wall-clock in tz_name, returned as UTC.
    """
    if long_video_date.tzinfo is None:
        long_video_date = long_video_date.replace(tzinfo=timezone.utc)
    tz = get_tz(tz_name)
    local_long = long_video_date.astimezone(tz)
    t = parse_time(default_time)

    if next_long_date is None:
        return [local_to_utc(local_long.date(), t, tz_name)]

    if next_long_date.tzinfo is None:
        next_long_date = next_long_date.replace(tzinfo=timezone.utc)
    local_next = next_long_date.astimezone(tz)
    end_day = local_next.date() - timedelta(days=1)
    if end_day < local_long.date():
        end_day = local_long.date()

    return [
        local_to_utc(d, t, tz_name)
        for d in daterange_dates(local_long.date(), end_day)
    ]


def distribute_shorts(
    short_ids: list[int],
    slot_times: list[datetime],
    min_interval_minutes: int,
) -> list[tuple[int, datetime]]:
    if not short_ids or not slot_times:
        return []

    from collections import defaultdict
    by_date: dict = defaultdict(list)
    for st in sorted(slot_times):
        by_date[st.date()].append(st)

    result: list[tuple[int, datetime]] = []
    idx = 0
    interval = timedelta(minutes=min_interval_minutes)
    days_sorted = sorted(by_date.keys())

    for di, day in enumerate(days_sorted):
        base = by_date[day][0]
        offset = timedelta(0)
        while idx < len(short_ids):
            result.append((short_ids[idx], base + offset))
            idx += 1
            offset += interval
            remaining_days = len(days_sorted) - di - 1
            remaining_shorts = len(short_ids) - idx
            if remaining_days > 0 and remaining_shorts > 0 and offset >= interval * 2:
                break
        if idx >= len(short_ids):
            break
    return result


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
        from_dt = from_dt.replace(tzinfo=timezone.utc)
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
