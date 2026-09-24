# Grok — старт здесь

Этот файл — быстрый вход для Grok (исполнителя доработки). Правила обязательны.
Репозиторий публичный: https://github.com/cryptoigor007/postiz-orchestrator

## Объём: ВСЕ модули сразу
См. `docs/dev/07_GROK_TASK.txt` §0.1: сделать сразу ВСЕ модули, без ожидания
подтверждений между ними:
YouTube (эталон) → Telegram → Postiz-адаптер → Instagram → TikTok (inbox v1) →
Facebook → Threads → пакет аудита TikTok.
После каждого модуля: unit-тесты → `./scripts/check.sh` зелёный → commit → следующий.
В ПРОД ничего не включать до этапа P5 (engines остаются postiz/direct).

## Что читать (по порядку)
1. `AGENTS.md` — протокол работы: репро → правка → `./scripts/check.sh` → deploy → живая
   проверка → запись в `docs/SESSION_LOG.md`; сторож Telegram; «вылизывать всегда».
2. `docs/dev/00_INDEX.txt` — навигация по документации.
3. `docs/dev/07_GROK_TASK.txt` — ПОЛНАЯ задача (пакеты 1–7; §0.1 — объём «все модули»).
4. `docs/dev/08_ОТВЕТ_НА_АНАЛИЗ.txt` — факты по схеме БД и решения по P1/P2.
5. `docs/dev/06_HANDOFF.txt` — состояние, команды, доступы (без секретов).
6. `docs/dev/02_MODULE_STANDARD.txt` + `docs/dev/03_API_STANDARDS.txt` + `docs/dev/04_DECISIONS.txt`.
7. ТЗ платформы: `docs/modules/MODULE_<PLATFORM>.txt` (YouTube — эталон структуры).

## Текущее состояние (обновлять по мере работы)
- Версия ядра 8.4.55; Э1 (каркас модулей) и P1 (force_update + watchdog-алерты) влиты.
- `module:youtube` в проде ВЫКЛЮЧЕН: включать только на этапе P5 после contract-прогона.
- Тесты: `./scripts/check.sh` → ALL CHECKS PASSED (565 тестов на 24.09.2026).

## Нельзя
- Коммитить секреты (`config.yaml`, `.env`, токены); менять схему БД иначе как ADD COLUMN;
  включать модули в проде до P5; выдумывать факты (неуверенное — «проверить»).
- Заявлять «готово» без вывода проверок.
