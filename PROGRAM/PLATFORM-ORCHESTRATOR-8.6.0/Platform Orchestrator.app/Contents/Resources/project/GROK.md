# Grok — старт здесь

> **HARD_CUT (module path only).** Postiz VM / HTTP transport / `POSTIZ_*` env — **не required**.
> Runtime: `engines.<platform>=module:<id>`. Gate: `scripts/gate_platform_zero.sh`.
> Быстрый вход: `START.md` · площадки: `docs/PLATFORM_SETUP.md` · статус: `REPORT-HARD-CUT.txt`.


## Объём: ВСЕ модули сразу
См. `docs/dev/07_GROK_TASK.txt` §0.1: сделать сразу ВСЕ модули, без ожидания
подтверждений между ними:
YouTube (эталон) → Telegram → Postiz-адаптер → Instagram → TikTok (inbox v1) →
Facebook → Threads → пакет аудита TikTok.
После каждого модуля: unit-тесты → `./scripts/check.sh` зелёный → commit → следующий.
HARD_CUT: в проде module path; postiz/direct не required runtime.

## Что читать (по порядку)
1. `AGENTS.md` — протокол работы: репро → правка → `./scripts/check.sh` → deploy → живая
   проверка → запись в `docs/SESSION_LOG.md`; сторож Telegram; «вылизывать всегда».
2. `docs/dev/00_INDEX.txt` — навигация по документации.
3. `docs/dev/07_GROK_TASK.txt` — ПОЛНАЯ задача (пакеты 1–7; §0.1 — объём «все модули»).
4. `docs/dev/08_ОТВЕТ_НА_АНАЛИЗ.txt` — факты по схеме БД и решения по P1/P2.
5. `docs/dev/06_HANDOFF.txt` — состояние, команды, доступы (без секретов).
6. `docs/dev/02_MODULE_STANDARD.txt` + `docs/dev/03_API_STANDARDS.txt` + `docs/dev/04_DECISIONS.txt`.
7. ТЗ платформы: `docs/modules/MODULE_<PLATFORM>.txt` (YouTube — эталон структуры).
8. `docs/dev/09_YT_SCRIPTS_TZ.txt` — ТЗ на YouTube-CLI («руки» ассистента: все операции
   YouTube через shell). Отдельная задача; порядок — по указанию владельца.

## Текущее состояние (обновлять по мере работы)
- Версия ядра 8.4.55; Э1 (каркас модулей) и P1 (force_update + watchdog-алерты) влиты.
- `module:youtube` / остальные modules — путь публикации (см. config.example.yaml).
- Тесты: `bash scripts/gate_platform_zero.sh` + `pytest tests/ -q` (см. REPORT-HARD-CUT.txt).

## Нельзя
- Коммитить секреты (`config.yaml`, `.env`, токены); менять схему БД иначе как ADD COLUMN;
  включать модули в проде до P5; выдумывать факты (неуверенное — «проверить»).
- Заявлять «готово» без вывода проверок.
