Telegram module v1.0.0
======================
Контракт PlatformModule: publish (at_slot), update_metadata (editMessageText),
delete, auth_status (getMe+getChat). early_upload / schedule_publish — NotSupported.

Основной сценарий: post_mode=link — HTML-текст + link_preview_options.show_above_text
+ inline-кнопка на YouTube.

Токен: TELEGRAM_BOT_TOKEN (.env 600). chat_id: platforms.telegram.publish_chat_id
или TELEGRAM_PUBLISH_CHAT_ID / deps фабрики.

Включение в прод: engines.telegram=module:telegram — ТОЛЬКО на этапе P5.
До P5: unit + dry-run; live contract — после [ВЛАДЕЛЕЦ].

Тесты: tests/test_telegram_module.py
ТЗ: docs/modules/MODULE_TELEGRAM.txt
