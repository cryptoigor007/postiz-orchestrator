"""Пробный (тестовый) пост: отдельный контур E2E-проверки.

Ключевое свойство: тест НЕ трогает боевые строки `entity_platform_status`
(не подменяет и не удаляет запланированные посты). Пост создаётся напрямую
в Postiz, факт фиксируется в `publish_log` (action='test_scheduled').
Разрешён только по явному allowlist платформ и только если контур включён.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def _metric(comps: dict[str, Any], key: str, n: int = 1) -> None:
    """P2.7: безопасный инкремент метрики (metrics может отсутствовать в comps)."""
    metrics = comps.get("metrics")
    if metrics is not None and hasattr(metrics, "incr"):
        try:
            metrics.incr(key, n)
        except Exception:
            pass


class TestPublishError(Exception):
    """Ошибка тестового поста (валидация/лимиты) — с кодом ответа для API."""

    __test__ = False

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


def _resolve_entity(db, entity_type: str, entity_id: int) -> dict:
    if entity_type == "long_video":
        row = db.fetchone("SELECT * FROM long_videos WHERE id=?", (entity_id,))
    elif entity_type == "short":
        row = db.fetchone("SELECT * FROM shorts WHERE id=?", (entity_id,))
    else:
        raise TestPublishError("entity_type must be long_video|short", 400)
    if not row:
        raise TestPublishError(f"{entity_type}#{entity_id} not found", 404)
    return dict(row)


def _youtube_url(db, entity_type: str, entity_id: int) -> str:
    """Ссылка на YouTube-выпуск сущности (для link-режима)."""
    row = db.fetchone(
        "SELECT release_url FROM entity_platform_status WHERE entity_type=? AND entity_id=? "
        "AND platform='youtube' AND coalesce(release_url,'')<>'' LIMIT 1",
        (entity_type, entity_id))
    return (row or {}).get("release_url") or ""


def _pick_media(row: dict, platform: str, pcfg) -> str | None:
    """Путь медиа под платформу: platform_paths → wide/vertical → video_path."""
    import json as _json
    try:
        pm = _json.loads(row.get("platform_paths") or "{}")
        if isinstance(pm, dict) and pm.get(platform):
            return pm[platform]
    except Exception:
        pass
    if row.get("wide_path") or row.get("vertical_path"):
        variant = getattr(pcfg, "video_variant", "wide")
        return row.get("wide_path") if variant == "wide" else row.get("vertical_path")
    return row.get("video_path")


def schedule_test_post(
    comps: dict[str, Any],
    *,
    platform: str,
    entity_type: str,
    entity_id: int,
    delay_minutes: int | None = None,
    scheduled_for: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Создать пробный пост в Postiz через ~N минут, не трогая боевую очередь."""
    cfg = comps["cfg"]
    db = comps["db"]
    clock = comps["clock"]
    tcfg = cfg.test_publish

    if not tcfg.enabled:
        raise TestPublishError("test_publish disabled", 403)

    pcfg = cfg.platforms.get(platform)
    if not pcfg or not getattr(pcfg, "enabled", False):
        raise TestPublishError(f"platform {platform} is not enabled", 400)
    if tcfg.require_explicit_platforms and platform not in (tcfg.platforms or []):
        raise TestPublishError(f"platform {platform} not in test allowlist", 403)

    iid = getattr(pcfg, "integration_id", "") or ""
    if not tcfg.allow_prod_channel:
        if iid and iid in (tcfg.prod_integration_ids or []):
            raise TestPublishError("prod channel is not allowed for test posts", 403)
        # fail-closed: тест разрешён только для id из allowlist (пустой список = запрет)
        if not tcfg.test_integration_ids:
            raise TestPublishError("test_integration_ids not configured (fail-closed)", 403)
        if iid not in (tcfg.test_integration_ids or []):
            raise TestPublishError(f"integration {iid or '<empty>'} not in test allowlist", 403)

    now = clock.now()
    if scheduled_for:
        try:
            when = datetime.fromisoformat(str(scheduled_for).replace("Z", "+00:00"))
        except Exception as e:
            raise TestPublishError(f"bad scheduled_for: {e}", 400) from e
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        if when <= now:
            raise TestPublishError("scheduled_for must be in the future", 400)
    else:
        delay = int(delay_minutes if delay_minutes is not None else tcfg.default_delay_minutes)
        if delay < int(tcfg.min_delay_minutes) or delay > int(tcfg.max_delay_minutes):
            raise TestPublishError(
                f"delay_minutes must be within [{tcfg.min_delay_minutes}, {tcfg.max_delay_minutes}]",
                400)
        when = now + timedelta(minutes=delay)

    row = _resolve_entity(db, entity_type, entity_id)
    title = f"{tcfg.title_prefix}{row.get('title_text') or row.get('title') or entity_id}"
    desc = (row.get("description_text") or "").strip()

    media = None
    if getattr(pcfg, "post_mode", "media") == "link":
        # link-режим (как боевой telegram): шлём ссылку на YouTube, медиа не грузим
        url = _youtube_url(db, entity_type, entity_id)
        if not url:
            raise TestPublishError(
                "link-режим: нет YouTube-ссылки у сущности (сначала опубликуйте видео)", 400)
        desc = f"{title}\n\n▶ Полное видео: {url}"
    else:
        media = _pick_media(row, platform, pcfg)
        if not media:
            raise TestPublishError("no media for entity/platform", 400)
        # Bot API Telegram не принимает файлы >50 МБ (боевой контур шлёт ссылки, не видео)
        if platform == "telegram":
            import os as _os
            try:
                size_mb = _os.path.getsize(media) / (1024 * 1024)
            except OSError:
                size_mb = 0
            if size_mb > 45:
                raise TestPublishError(
                    f"telegram: файл {size_mb:.0f} МБ > 45 МБ (лимит Bot API) — "
                    "укажите ссылку (post_mode=link) или меньшее видео", 400)
        desc = (f"{title}\n\n{desc}".strip() if desc else title)

    content: dict[str, Any] = {
        "title": title,
        # префикс и в теле сообщения: на telegram message = description (title игнорируется)
        "description": desc,
        "hashtags": row.get("hashtags_text") or "",
        "cover": row.get("cover_path") or "",
        "integration_id": iid,
    }

    safety = comps.get("safety")
    if safety is not None:
        # P1.2: тест не расходует боевые лимиты (daily_limit/min_interval),
        # но пауза платформы уважается всегда
        if getattr(tcfg, "ignore_limits", True):
            try:
                if safety.is_platform_paused(platform):
                    raise TestPublishError("safety: platform_paused", 409)
            except AttributeError:
                pass
        else:
            ok, reason = safety.can_schedule(platform, when, pcfg.daily_limit)
            if not ok:
                raise TestPublishError(f"safety: {reason}", 409)

    if dry_run:
        db.log(entity_type, entity_id, platform, "test_dry_run",
               f"would schedule {when.isoformat()}")
        return {"ok": True, "dry_run": True, "platform": platform,
                "entity_type": entity_type, "entity_id": entity_id,
                "scheduled_for": when.isoformat(), "media": media}

    from .media import make_media

    postiz = comps.get("postiz")
    if postiz is None:
        raise TestPublishError("postiz unavailable", 500)
    broker = comps.get("broker")
    ref = make_media(media, platform, cfg, postiz, broker) if media else None
    post = postiz.create_post(platform=platform, media=ref, content=content,
                              scheduled_for=when)
    db.log(entity_type, entity_id, platform, "test_scheduled",
           f"{post.id} @ {when.isoformat()}")
    _metric(comps, "test_scheduled")
    logger.info("test post scheduled: %s/%s %s -> %s @ %s",
                entity_type, entity_id, platform, post.id, when.isoformat())
    return {"ok": True, "dry_run": False, "platform": platform,
            "entity_type": entity_type, "entity_id": entity_id,
            "postiz_post_id": post.id, "scheduled_for": when.isoformat()}


def cleanup_expired_test_posts(comps: dict[str, Any]) -> int:
    """P1.3: снять из Postiz тест-посты старше cleanup_after_hours (не трогая боевые)."""
    db = comps["db"]
    tcfg = comps["cfg"].test_publish
    ttl = int(getattr(tcfg, "cleanup_after_hours", 0) or 0)
    if ttl <= 0:
        return 0
    postiz = comps.get("postiz")
    if postiz is None:
        return 0
    from datetime import UTC as _UTC

    active: dict[str, str] = {}
    for r in db.fetchall("SELECT details, created_at FROM publish_log "
                         "WHERE action='test_scheduled'"):
        pid = (r["details"] or "").strip().split(" ", 1)[0]
        if pid:
            active[pid] = r["created_at"] or ""
    for r in db.fetchall("SELECT details FROM publish_log WHERE action='test_cancelled'"):
        active.pop((r["details"] or "").strip(), None)
    now = comps["clock"].now()
    n = 0
    for pid, created in active.items():
        try:
            ts = datetime.fromisoformat(created)
        except Exception:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=_UTC)
        if (now - ts).total_seconds() < ttl * 3600:
            continue
        try:
            postiz.delete_post(pid)
        except Exception:
            logger.warning("test auto-cleanup: delete %s failed", pid, exc_info=True)
            continue
        db.log("system", None, "", "test_auto_cancelled", pid)
        n += 1
    if n:
        logger.info("Test auto-cleanup: removed %s expired test post(s)", n)
    return n


def test_recent(db, limit: int = 10) -> list[dict]:
    """Последние пробные посты из publish_log (кроме dry-run)."""
    rows = db.fetchall(
        "SELECT entity_type, entity_id, platform, details, created_at FROM publish_log "
        "WHERE action='test_scheduled' ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


def cancel_test_post(comps: dict[str, Any], postiz_post_id: str) -> dict[str, Any]:
    """Удалить пробный пост из Postiz (только если он помечен как тестовый)."""
    db = comps["db"]
    # Точное сравнение post id (первый токен details): префикс не должен матчить чужой пост
    marked = False
    for r in db.fetchall("SELECT details FROM publish_log WHERE action='test_scheduled'"):
        pid = (r["details"] or "").strip().split(" ", 1)[0]
        if pid and pid == postiz_post_id:
            marked = True
            break
    if not marked:
        raise TestPublishError("post is not a test post", 404)
    postiz = comps.get("postiz")
    if postiz is None:
        raise TestPublishError("postiz unavailable", 500)
    postiz.delete_post(postiz_post_id)
    db.log("system", None, "", "test_cancelled", postiz_post_id)
    _metric(comps, "test_cancelled")
    return {"ok": True, "deleted": postiz_post_id}
