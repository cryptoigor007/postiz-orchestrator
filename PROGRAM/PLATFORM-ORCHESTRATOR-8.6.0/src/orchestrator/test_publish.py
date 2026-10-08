"""Пробный (тестовый) пост: отдельный контур E2E-проверки.

Ключевое свойство: тест НЕ трогает боевые строки `entity_platform_status`
(не подменяет и не удаляет запланированные посты). Пост создаётся через
platform module path, факт фиксируется в `publish_log` (action='test_scheduled').
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
        except Exception as exc:
            logger.debug("test publish helper failed: %s", type(exc).__name__)


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
    except Exception as exc:
        logger.debug("platform_paths parse failed: %s", type(exc).__name__)
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
    """Создать пробный пост в platform через ~N минут, не трогая боевую очередь."""
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

    iid = (getattr(pcfg, "account_id", "") or getattr(pcfg, "integration_id", "") or "")
    if not tcfg.allow_prod_channel:
        prod_ids = list(getattr(tcfg, "prod_account_ids", None) or getattr(tcfg, "prod_integration_ids", None) or [])
        if iid and iid in prod_ids:
            raise TestPublishError("prod channel is not allowed for test posts", 403)
        # fail-closed: тест разрешён только для id из allowlist (пустой список = запрет)
        test_ids = list(getattr(tcfg, "test_account_ids", None) or getattr(tcfg, "test_integration_ids", None) or [])
        if not test_ids:
            raise TestPublishError("test_account_ids not configured (fail-closed)", 403)
        if iid not in test_ids:
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
            except AttributeError as exc:
                logger.debug("test publish safety helper unavailable: %s", type(exc).__name__)
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

    # Live: module path only (platform transport removed).
    external_id = _module_publish_test(
        comps, platform=platform, media=media, content=content, scheduled_for=when,
    )
    db.log(entity_type, entity_id, platform, "test_scheduled",
           f"{external_id} @ {when.isoformat()}")
    _metric(comps, "test_scheduled")
    logger.info("test post scheduled: %s/%s %s -> %s @ %s",
                entity_type, entity_id, platform, external_id, when.isoformat())
    return {"ok": True, "dry_run": False, "platform": platform,
            "entity_type": entity_type, "entity_id": entity_id,
            "external_id": external_id, "scheduled_for": when.isoformat()}


def _module_publish_test(
    comps: dict[str, Any],
    *,
    platform: str,
    media: str | None,
    content: dict[str, Any],
    scheduled_for: datetime,
) -> str:
    """Publish test post via PlatformModule; does not touch entity_platform_status."""
    cfg = comps["cfg"]
    try:
        from .platforms import default_registry, resolve_engine
        from .platforms.base import MediaSpec, PublishMeta
    except Exception as e:
        raise TestPublishError(f"platforms unavailable: {e}", 500) from e

    eng = str(cfg.engine_for(platform) or "").strip()
    try:
        resolved = resolve_engine(eng)
    except ValueError as e:
        raise TestPublishError(str(e), 400) from e
    if resolved.kind != "module" or not resolved.module_id:
        raise TestPublishError(
            f"test_publish requires module engine for {platform}, got {eng!r}", 400)

    reg = comps.get("module_registry") or default_registry()
    if not reg.has(resolved.module_id):
        raise TestPublishError(f"module {resolved.module_id!r} not registered", 500)

    mod = reg.create(resolved.module_id, dry_run=bool(comps.get("test_module_dry_run", comps.get("module_registry") is not None)))
    meta = PublishMeta(
        title=content.get("title") or "",
        description=content.get("description") or "",
        hashtags=content.get("hashtags") or "",
        extra={"scheduled_for": scheduled_for.isoformat(), "test": True},
    )
    try:
        prepared = mod.prepare(MediaSpec(path=media or "", kind="video" if media else "text"))
        result = mod.publish(prepared, meta)
    except Exception as e:
        raise TestPublishError(f"module publish failed: {e}", 500) from e
    ext = getattr(result, "external_id", None) or getattr(result, "id", None) or ""
    if not ext:
        raise TestPublishError("module publish returned empty external_id", 500)
    # Best-effort schedule if module supports it and when is in the future
    try:
        if hasattr(mod, "schedule_publish") and scheduled_for > comps["clock"].now():
            mod.schedule_publish(str(ext), scheduled_for)
    except Exception:
        logger.debug("test schedule_publish not applied", exc_info=True)
    return str(ext)


def _module_delete(comps: dict[str, Any], external_id: str, platform: str = "") -> bool:
    """Best-effort delete via module; returns True if delete was attempted/ok."""
    try:
        from .platforms import default_registry, resolve_engine
    except Exception:
        return False
    cfg = comps.get("cfg")
    if cfg is None:
        return False
    # Try platform from log context or scan engines
    platforms = [platform] if platform else list((cfg.engines or {}).keys() or [])
    if not platforms:
        platforms = list((cfg.platforms or {}).keys())
    reg = comps.get("module_registry") or default_registry()
    for p in platforms:
        try:
            eng = str(cfg.engine_for(p) or "").strip()
            resolved = resolve_engine(eng)
            if resolved.kind != "module" or not resolved.module_id:
                continue
            if not reg.has(resolved.module_id):
                continue
            mod = reg.create(resolved.module_id, dry_run=False)
            if hasattr(mod, "delete"):
                mod.delete(external_id)
                return True
        except Exception:
            logger.debug("module delete %s on %s failed", external_id, p, exc_info=True)
    return False


def cleanup_expired_test_posts(comps: dict[str, Any]) -> int:
    """Remove expired test posts via module.delete when available; always log cancel."""
    db = comps["db"]
    tcfg = comps["cfg"].test_publish
    ttl = int(getattr(tcfg, "cleanup_after_hours", 0) or 0)
    if ttl <= 0:
        return 0
    from datetime import UTC as _UTC

    active: dict[str, tuple[str, str]] = {}  # pid -> (created_at, platform)
    for r in db.fetchall(
        "SELECT details, created_at, platform FROM publish_log "
        "WHERE action='test_scheduled'"
    ):
        pid = (r["details"] or "").strip().split(" ", 1)[0]
        if pid:
            active[pid] = (r["created_at"] or "", r.get("platform") or "")
    for r in db.fetchall(
        "SELECT details FROM publish_log "
        "WHERE action IN ('test_cancelled', 'test_auto_cancelled')"
    ):
        active.pop((r["details"] or "").strip(), None)
    now = comps["clock"].now()
    n = 0
    for pid, (created, platform) in active.items():
        try:
            ts = datetime.fromisoformat(created)
        except Exception:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=_UTC)
        if (now - ts).total_seconds() < ttl * 3600:
            continue
        _module_delete(comps, pid, platform)
        db.log("system", None, platform or "", "test_auto_cancelled", pid)
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


def cancel_test_post(
    comps: dict[str, Any],
    external_id: str | None = None,
    *,
    legacy_post_id: str | None = None,
) -> dict[str, Any]:
    """Delete test post via module (legacy alias: legacy_post_id → external_id)."""
    db = comps["db"]
    pid = (external_id or legacy_post_id or "").strip()
    if not pid:
        raise TestPublishError("external_id required", 400)
    marked = False
    platform = ""
    for r in db.fetchall(
        "SELECT details, platform FROM publish_log WHERE action='test_scheduled'"
    ):
        token = (r["details"] or "").strip().split(" ", 1)[0]
        if token and token == pid:
            marked = True
            platform = r.get("platform") or ""
            break
    if not marked:
        raise TestPublishError("post is not a test post", 404)
    _module_delete(comps, pid, platform)
    db.log("system", None, platform or "", "test_cancelled", pid)
    _metric(comps, "test_cancelled")
    return {"ok": True, "deleted": pid, "external_id": pid}
