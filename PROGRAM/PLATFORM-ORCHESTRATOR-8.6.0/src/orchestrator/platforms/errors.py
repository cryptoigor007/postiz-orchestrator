"""Единый словарь человекочитаемых ошибок модулей (решение A6 / 04_DECISIONS).

Сообщения на русском: что случилось + что делать.
Используется ботом, панелью и логами; коды — ModuleErrorCode.
"""

from __future__ import annotations

from .base import ModuleErrorCode

# code -> (короткое сообщение, действие)
ERROR_MESSAGES: dict[ModuleErrorCode, tuple[str, str]] = {
    ModuleErrorCode.AUTH_EXPIRED: (
        "Токен доступа истёк или отозван.",
        "Авто-refresh; если не помогло — переподключите аккаунт в панели.",
    ),
    ModuleErrorCode.AUTH_REQUIRED: (
        "Требуется повторная авторизация (refresh недействителен или отсутствует).",
        "Переподключите канал/страницу в панели (OAuth).",
    ),
    ModuleErrorCode.QUOTA: (
        "Суточная квота API платформы исчерпана.",
        "Пауза до сброса квоты; снизьте число загрузок.",
    ),
    ModuleErrorCode.RATE_LIMIT: (
        "Превышен лимит частоты запросов.",
        "Backoff по Retry-After; повторить позже.",
    ),
    ModuleErrorCode.MEDIA_INVALID: (
        "Невалидные метаданные или медиафайл.",
        "Проверьте title/description/файл (формат, размер, кодек).",
    ),
    ModuleErrorCode.PLATFORM_REJECTED: (
        "Платформа отклонила операцию (политика, верификация, права).",
        "См. детали в сообщении; для YouTube обложки — подтвердите канал телефоном.",
    ),
    ModuleErrorCode.CLAIM_BLOCKED: (
        "Контент заблокирован претензией (Content ID / права).",
        "Удалите или замените ролик; проверьте клейм в кабинете платформы.",
    ),
    ModuleErrorCode.TRANSIENT: (
        "Временная ошибка сети или сервера платформы.",
        "Повтор с backoff; при повторении — алерт владельцу.",
    ),
    ModuleErrorCode.FATAL: (
        "Неустранимая ошибка модуля или конфигурации.",
        "См. логи; проверьте external_id, конфиг и доступность модуля.",
    ),
}


def message_for(code: ModuleErrorCode | str, detail: str = "") -> tuple[str, str]:
    """Вернуть (message, action) для кода; detail дополняет message."""
    try:
        c = ModuleErrorCode(code)
    except ValueError:
        c = ModuleErrorCode.FATAL
    msg, action = ERROR_MESSAGES.get(c, ERROR_MESSAGES[ModuleErrorCode.FATAL])
    if detail:
        msg = f"{msg} {detail}".strip()
    return msg, action
