# Чеклист доведения Orchestrator до 10/10
Версия: 7.0.2 — ВЫПОЛНЕНО

## A. Критическая бизнес-логика
- [x] A1. release_url → refresh thematic (CREATE new → DELETE old)
- [x] A2. Ускоренная проверка fresh posts (sync fresh_only)
- [x] A3. serious_errors / auth_errors в config
- [x] A4. ShortsMaker standalone scanner в Watcher
- [x] A5. Orphan media tracking в HttpPostizClient

## B. Postiz-клиент
- [x] B1. Гибкий HttpPostizClient (поля + path env)
- [x] B2. create_postiz_client() factory

## C. Надёжность БД
- [x] C1. schema_version = 8
- [x] C2. Индексы platform/sched, status, parent

## D. Telegram
- [x] D1. force_link_update + link_upd wiring
- [x] D2. Тест команд handle_update

## E. Тесты и проверки
- [x] E1. refresh thematic with URL
- [x] E2. sync scheduled→published
- [x] E3. auth error → pause
- [x] E4. Все pytest зелёные
- [x] E5. Smoke --version / --once

## F. Документация
- [x] F1. README
- [x] F2. Версия 7.0.2
