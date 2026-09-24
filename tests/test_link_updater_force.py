"""Regression + unit tests for LinkUpdater.force_update (Пакет 1.1 / P1 v2).

Проверяем: force_update работает для любого entity_type (не только long_video),
при совпадении id (short/391 и long_video/391 — id независимы) выбирается запись
без release_url, при равенстве — long_video; явный entity_type выбирает точно;
thematic-refresh — только для long_video.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from orchestrator.link_updater import LinkUpdater


class FakeDB:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.updates: list[tuple] = []
        self.logs: list[tuple] = []

    def fetchone(self, sql: str, args: tuple = ()) -> dict | None:
        if "WHERE entity_type=?" in sql:  # явный тип
            etype, entity_id, platform = args
            for r in self.rows:
                if (
                    r["entity_type"] == etype
                    and r["entity_id"] == entity_id
                    and r["platform"] == platform
                ):
                    return r
            return None
        entity_id, platform = args[0], args[1]
        candidates = [
            r
            for r in self.rows
            if r["entity_id"] == entity_id and r["platform"] == platform
        ]
        if not candidates:
            return None
        # как ORDER BY в проде: сначала без release_url, затем long_video
        candidates.sort(
            key=lambda r: (
                0 if not r.get("release_url") else 1,
                0 if r.get("entity_type") == "long_video" else 1,
            )
        )
        return candidates[0]

    def execute(self, sql: str, args: tuple = ()) -> None:
        self.updates.append((sql, args))
        if "SET release_url" in sql and len(args) >= 5:
            new_url, _, entity_id, platform, entity_type = args
            for r in self.rows:
                if (
                    r["entity_id"] == entity_id
                    and r["platform"] == platform
                    and r.get("entity_type") == entity_type
                ):
                    r["release_url"] = new_url

    def log(
        self,
        entity_type: str,
        entity_id: int,
        platform: str,
        action: str,
        detail: str = "",
    ) -> None:
        self.logs.append((entity_type, entity_id, platform, action, detail))

    def fetchall(self, sql: str, args: tuple = ()) -> list:
        return []


def _row(
    entity_id: int,
    entity_type: str,
    platform: str = "youtube",
    release_url: str | None = None,
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "platform": platform,
        "postiz_post_id": f"{entity_type}-{entity_id}",
        "release_url": release_url,
    }


@pytest.fixture
def updater() -> LinkUpdater:
    db = FakeDB()
    cfg = MagicMock()
    cfg.description_templates = {"thematic_short": "{description}\n\n▶ {link}"}
    clock = MagicMock()
    clock.now.return_value = datetime(2026, 9, 24, 12, 0, 0)
    u = LinkUpdater(db=db, cfg=cfg, postiz=MagicMock(), clock=clock, tg=MagicMock())
    u._db = db  # convenience
    return u


def test_force_update_long_video(updater: LinkUpdater) -> None:
    db: FakeDB = updater.db  # type: ignore[assignment]
    db.rows.append(_row(100, "long_video"))
    assert updater.force_update(100, "youtube", "https://youtu.be/abc") is True
    assert db.logs == [
        ("long_video", 100, "youtube", "force_link_update", "https://youtu.be/abc")
    ]
    assert any("release_url" in u[0] for u in db.updates)


def test_force_update_short(updater: LinkUpdater) -> None:
    db: FakeDB = updater.db  # type: ignore[assignment]
    db.rows.append(_row(391, "short"))
    assert updater.force_update(391, "youtube", "https://youtu.be/short391") is True
    assert db.logs[0][0] == "short"
    assert db.logs[0][1] == 391


def test_force_update_collision_prefers_missing_url(updater: LinkUpdater) -> None:
    """Кейс 24.09: short/391 без ссылки, long_video/391 с чужой ссылкой → чиним short."""
    db: FakeDB = updater.db  # type: ignore[assignment]
    db.rows.append(_row(391, "short"))
    db.rows.append(_row(391, "long_video", release_url="https://youtu.be/old"))
    assert updater.force_update(391, "youtube", "https://youtu.be/new") is True
    assert db.logs[0][0] == "short"
    short = next(r for r in db.rows if r["entity_type"] == "short")
    assert short["release_url"] == "https://youtu.be/new"


def test_force_update_collision_both_empty_prefers_long_video(
    updater: LinkUpdater,
) -> None:
    db: FakeDB = updater.db  # type: ignore[assignment]
    db.rows.append(_row(7, "short"))
    db.rows.append(_row(7, "long_video"))
    assert updater.force_update(7, "youtube", "https://youtu.be/x") is True
    assert db.logs[0][0] == "long_video"


def test_force_update_explicit_entity_type(updater: LinkUpdater) -> None:
    db: FakeDB = updater.db  # type: ignore[assignment]
    db.rows.append(_row(391, "short"))
    db.rows.append(_row(391, "long_video"))
    assert (
        updater.force_update(
            391, "youtube", "https://youtu.be/sh", entity_type="short"
        )
        is True
    )
    assert db.logs[0][0] == "short"


def test_force_update_missing_id(updater: LinkUpdater) -> None:
    assert updater.force_update(99999, "youtube", "https://youtu.be/x") is False


def test_force_update_rejects_non_http(updater: LinkUpdater) -> None:
    db: FakeDB = updater.db  # type: ignore[assignment]
    db.rows.append(_row(1, "long_video"))
    assert updater.force_update(1, "youtube", "ftp://bad") is False
    assert updater.force_update(1, "youtube", "not-a-url") is False
