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
