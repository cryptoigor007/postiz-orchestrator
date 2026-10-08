"""daily_ahead job (решение A2 / 04_DECISIONS).

Ежедневно (по умолчанию 09:00): убедиться, что видео на сегодня+завтра
загружены (private + publishAt) через module:youtube; без дублей.

В проде вызывается из scheduler/jobs — здесь чистая функция для unit.
НЕ включает engines; только если передан youtube_module.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class _YoutubeLike(Protocol):
    def upload(self, media: Any, meta: Any, when: datetime | None = None) -> Any: ...


@dataclass
class AheadItem:
    path: str
    title: str
    slot: datetime
    external_id: str | None = None  # уже есть в БД


@dataclass
class AheadResult:
    uploaded: int = 0
    skipped: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def plan_horizon(today: date | None = None, days: int = 2) -> list[date]:
    """Сегодня + (days-1) следующих дней."""
    base = today or datetime.now(UTC).date()
    return [base + timedelta(days=i) for i in range(max(1, days))]


def run_daily_ahead(
    items: list[AheadItem],
    youtube_module: _YoutubeLike | None,
    *,
    dry_run: bool = True,
    make_meta: Callable[[AheadItem], Any] | None = None,
    make_media: Callable[[AheadItem], Any] | None = None,
) -> AheadResult:
    """Загрузить недостающие (без external_id). Идемпотентно по external_id."""
    from .platforms.base import PreparedMedia, PublishMeta

    result = AheadResult()
    if youtube_module is None:
        result.errors.append("youtube_module не передан — daily_ahead noop")
        return result
    for it in items:
        if it.external_id:
            result.skipped += 1
            continue
        meta = make_meta(it) if make_meta else PublishMeta(title=it.title)
        media = make_media(it) if make_media else PreparedMedia(path=it.path, kind="video")
        if dry_run:
            logger.info("daily_ahead dry-run would upload %s at %s", it.path, it.slot)
            result.uploaded += 1
            continue
        try:
            youtube_module.upload(media, meta, when=it.slot)
            result.uploaded += 1
        except Exception as e:
            result.errors.append(f"{it.path}: {e}")
    return result



@dataclass
class QuotaBuckets:
    """YouTube two-bucket accounting (not cost_upload 1600)."""
    upload_bucket: int = 100   # upload-related units per day
    general_bucket: int = 10000
    used_upload: int = 0
    used_general: int = 0

    def can_upload(self, cost: int = 1) -> bool:
        return (self.used_upload + cost) <= self.upload_bucket

    def reserve_upload(self, cost: int = 1) -> bool:
        if not self.can_upload(cost):
            return False
        self.used_upload += cost
        return True


def run_daily_ahead_with_quota(
    items: list[AheadItem],
    youtube_module: _YoutubeLike | None,
    quota: QuotaBuckets | None = None,
    *,
    dry_run: bool = True,
    posts_per_day: int | None = None,
) -> AheadResult:
    """Module-only daily_ahead with optional two-bucket quota reserve.

    posts_per_day is a safety cap (config), independent of upload_bucket 100.
    """
    result = AheadResult()
    if youtube_module is None:
        result.errors.append("youtube_module не передан — daily_ahead noop")
        return result
    q = quota or QuotaBuckets()
    uploaded_today = 0
    for it in items:
        if it.external_id:
            result.skipped += 1
            continue
        if posts_per_day is not None and uploaded_today >= posts_per_day:
            result.skipped += 1
            continue
        if not q.reserve_upload(1):
            result.errors.append(f"quota upload_bucket exhausted at {it.path}")
            break
        if dry_run:
            result.uploaded += 1
            uploaded_today += 1
            continue
        try:
            from .platforms.base import PreparedMedia, PublishMeta
            youtube_module.upload(
                PreparedMedia(path=it.path, kind="video"),
                PublishMeta(title=it.title),
                when=it.slot,
            )
            result.uploaded += 1
            uploaded_today += 1
        except Exception as e:
            result.errors.append(f"{it.path}: {e}")
    return result
