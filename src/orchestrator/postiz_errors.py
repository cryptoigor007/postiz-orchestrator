"""Разбор причин ошибок Postiz (публичный API `/public/v1/notifications`).

Зачем отдельный модуль. В объекте поста Postiz отдаёт только `state=ERROR`
(`GET /public/v1/posts` возвращает id/content/state/releaseURL — без текста ошибки,
single-get `/public/v1/posts/{id}` в этой сборке вообще 404). Человекочитаемая
причина лежит в уведомлениях Postiz:

    "An error occurred while posting on youtube: Your account is not verified,
     we have uploaded your video but we could not set the thumbnail. ..."

Именно оттуда её и берёт `StatusSync`, чтобы записать в `last_error`
(см. INCIDENT-2026-09-23-battery-guard.md и docs/SESSION_LOG.md).
"""

from __future__ import annotations

# «An error occurred while posting on <platform>: <reason>»
_ERROR_MARKER = "error occurred while posting on"

# Ошибка только обложки: видео уже загружено, не встала лишь миниатюра.
_THUMBNAIL_ONLY_HINTS = (
    "could not set the thumbnail",
    "couldn't set the thumbnail",
    "failed to set the thumbnail",
    "unable to set the thumbnail",
    "cannot set the thumbnail",
    "thumbnail could not be set",
)


def _squash(text: object) -> str:
    """Однострочный текст: уведомления приходят с переносами и лишними пробелами."""
    return " ".join(str(text or "").split())


def parse_error_notification(content: object) -> tuple[str, str] | None:
    """Разобрать уведомление Postiz.

    Возвращает `(platform, reason)` для ошибки публикации и `None`, если это не ошибка
    (например «Your post has been published on Youtube at …»). Платформа может быть
    пустой строкой — у части уведомлений её в тексте нет.
    """
    text = _squash(content)
    if not text:
        return None
    low = text.lower()
    pos = low.find(_ERROR_MARKER)
    if pos >= 0:
        rest = text[pos + len(_ERROR_MARKER):].strip()
        platform, sep, reason = rest.partition(":")
        if sep:
            return platform.strip().lower(), reason.strip() or text
        return "", rest or text
    if "error" in low and "post" in low:
        # незнакомый формат, но по смыслу — ошибка публикации: отдаём текст как есть
        return "", text
    return None


def is_thumbnail_only_error(reason: object) -> bool:
    """Это ошибка «видео загрузилось, а обложка не встала»?

    Такая публикация состоялась: пост нельзя помечать провалом (канал просто не
    подтверждён — Postiz не даёт поставить кастомную миниатюру).
    """
    low = _squash(reason).lower()
    if not low:
        return False
    if any(hint in low for hint in _THUMBNAIL_ONLY_HINTS):
        return True
    return "thumbnail" in low and "not verified" in low


def short_reason(reason: object, limit: int = 300) -> str:
    """Причина для панели: без переносов и в разумной длине."""
    text = _squash(reason)
    if limit > 0 and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text
