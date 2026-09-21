# Отчёт 8.2.1 — Residual closure (P0/P1/P2). Честный отчёт: что исправлено, что нет

**Дата:** 2026-09-21 · **Версия:** 8.2.1 · **Сборка:** b815 · **Коммит:** `66b2050` (master, запушен)
**Тесты:** 304 (было 255; +49) · **ruff:** 0 · `check.sh`: PASS · `gui_check.sh` (боевой сервер): PASS
**Бэкап отката:** `/root/orchestrator_rollback_20260921_133459.tar.gz` (снят перед 8.2.0; текущий деплой — тем же deploy-путём)

## 1. P0 — закрыто кодом + тестами

| # | Дефект | Фикс | Тесты |
|---|--------|------|-------|
| P0.1 | SSRF TOCTOU, тело целиком в RAM, hostname-трюки | `_fetch_image_pinned`: resolve+валидация **всех** A/AAAA, **pin IP** при connect (TLS SNI = hostname), ручные redirect-хопы ≤3 с ревалидацией и relative-join, **stream cap 25 MiB** (до/во время чтения), отказ `localhost/*.localhost/*.local`, decimal/hex/octal/dotted-quad литералов, userinfo, не-http(s) схем | `tests/test_ssrf_pin.py` (22): rebind (коннект только на проверенный IP), redirect→private, oversize (Content-Length и стрим), схемы, литералы |
| P0.2 | пустой prod-guard (`prod_integration_ids: []`) | `test_integration_ids` allowlist + **fail-closed** (пусто = запрет), prod-overlap по-прежнему блокируется; в config.yaml внесены наши тест-каналы | +1 тест (empty/чужой/свой id/allow_prod) |
| P0.3 | orphan_media API | **уже было** (методы + вызовы в publisher/runner + тесты) — проверено, не переделывал | `test_all_remaining.py` |
| P0.4 | отмена тест-поста по `LIKE prefix%` | точное сравнение post id (первый токен details) | +1 (коллизия префикса) |
| P0.5 | replay старого initData | freshness `auth_date` (`ORCH_WEBAPP_INIT_MAX_AGE_SEC`, default 86400; отсутствие auth_date = отказ) | +1 (свежий/старый/без hash) |
| P0.6 | XSS в UI | **37** вставок данных API/ФС обёрнуты в `esc()` (cover picker, folders, browse, queue-edit, manual, claims, errors, `data-p`, `href`, busy/busyJob) | gui_check (боевой); ручной grep-пасс |
| P0.7 | нет капа тела POST | 413 **до** `rfile.read` (`ORCH_MAX_BODY_BYTES`, default 50 MiB) | +1 (413) |
| P0.8 | тест-посты считались сиротами | активные `test_scheduled` (минус `test_cancelled`) исключены из `cleanup_orphans` и `Reconciliation` | +2 (+ live: cleanup → `deleted: 0`) |
| P0.9 | soft-end и backlog делили поля | **schema v13**: `pending_backlog_question/_at`; миграция переносит старые pending (эвристика: их ставил только backlog) и чистит series_end | +3 (независимость, tail-reset, миграция v13) |
| P0.10 | backlog-слоты из сырого конфига | `effective()` (override/группы/исключения) в `next_long_slot`/`last_long_slot` | +2 (override sun 10:00, блок scheduler) |
| P0.11 | `ask_series_end` без pending-диалога | диалог ставится на все allowed-чаты; ответ «да» чистит pending + включает хвост | +1 |
| **N1** | **реальный дефект**: `ask_backlog/remind_backlog/backlog_distributed/broadcast_markup` были вложены в `setup_commands` и вызывались через несуществующий `self` → **вопрос об остатке серии молча не отправлялся** (AttributeError глотался в BacklogManager) | вынесены на класс `TelegramNotifier`; `ask_backlog` реально работает | +1 (методы на классе) + live-impl проверка |

**Признание ошибки:** сначала (по первому grep) я заключил, что N1 — не баг. Это было **неверно**: проверка через `getattr(TelegramNotifier, ...)` показала отсутствие методов, а `self` внутри них был неразрешим. Дефект исправлен по-настоящему.

## 2. P1 — закрыто

| # | Дефект | Фикс | Тесты |
|---|--------|------|-------|
| P1.1 | DELETE/PUT без ретраев; 429 без Retry-After | DELETE/PUT через `_request_with_retry`; `Retry-After` clamp 1–60 для 429 | +3 |
| P1.2 | тест жёг боевые лимиты | `ignore_limits: true` — тест не расходует daily_limit/min_interval, **пауза платформы уважается** (409) | +1 |
| P1.3/11 | тест-посты копились | `cleanup_after_hours: 24`; цикл runner (раз в час) снимает просроченные, логирует `test_auto_cancelled` | +1 (старый снят, свежий и боевой целы) |
| P1.4 | pause/resume без строки состояния | UPSERT/INSERT-OR-NOTHING | +1 |
| P1.5 | sync-скрипт: ручной JSON, слепой curl, рестарт всегда | JSON через python3, проверка ответа Telegram (лог ошибок), рестарт только при несовпадении env процесса | live: деплой → 815?key=… |
| P1.6 | CI без migrations smoke | отдельный шаг + `tests/test_migrations.py` (fresh/v11/v13/идемпотентность/дубли) | 4 |
| P1.7 | config несогласован | `backup.method: sqlite_backup`; комментарий к `postiz_create_per_hour: 60` (реальный троттлинг ~30/час) | — |
| P1.8 | rate-limit identity = полный Init-Data (меняется всегда → лимит не работал) | identity: access-key → user id из initData → первый XFF → anon | +1 |
| P1.9 | YT delete мог «врать» | **проверено**: `urlopen` бросает на ошибке → True только при успехе; добавлен docstring и тест на исключение | +1 |
| P1.10 | transport игнорировал ответ Bot API | проверка `status`+`ok`, лог тела при ошибке, backoff на 429 (retry_after, clamp 1–60) + один повтор | — (живой путь не форсировали) |

## 3. P2 — закрыто (или честно помечено)

- **P2.1** изоляция тест-контура: тест с «BoomScheduler/BoomTail» — раскладка/тематика/хвост не вызываются (+ флаги `skip_*`, `zero_jitter` подтверждены).
- **P2.2** README/HANDOFF → 8.2.1/b815/304; секретов в доках нет (только имена env-переменных).
- **P2.3** CHANGELOG: 4 дублирующихся `# Changelog` → один заголовок + секция 8.2.1.
- **P2.4** CSP: `unsafe-inline` оставлен с явным TODO (инлайн-скрипт панели); все данные через `esc()`.
- **P2.5** watcher: мягкое FIFO-вытеснение кэша размеров вместо `clear()`.
- **P2.6** MCP: `orch_test_schedule` / `orch_test_status` / `orch_test_cancel`.
- **P2.7** метрики `test_scheduled` / `test_cancelled` / `test_rejected`; `Metrics` теперь общий в `comps` (API и runner пишут в один файл).
- **P2.8** `media.telegram_max_mb` — **проверено**: уже единый через `make_media` (N5 аудита подтверждён); в тест-контуре дополнительно жёсткий кап 45 МБ (Bot API).
- **P2.9** overflow: документирован смысл «skipped на всех платформах конфига» + `overflow_move_files=false`.
- **P2.10** `ORCH_GUARD_TTL_SEC` проброшен в `ScheduleGuard(ttl_sec=...)`.

## 4. Живой E2E после 8.2.1 (боевой сервер)

1. Деплой: `8.2.1`, b815, сервис active; **миграция schema v13 на живой БД прошла** (13), 82 строки `entity_platform_status` — без изменений.
2. Панель `/webapp/b/815/?key=…` → 200; GUI-проверка (поиск, папки, JS-ошибок нет) — PASS; меню-кнопка синхронизирована на 815.
3. Тест-пост (youtube, short 270, +1 мин): `cmub5vdgw…` → **PUBLISHED** `https://www.youtube.com/watch?v=6HW23NkJMrg`, тело начинается с `[orch-test]`; затем `/test/cancel` → `{"ok": true}`.
4. `cleanup_orphans` при активном тест-посте → `deleted: 0` (P0.8 работает).
5. Боевые счётчики после всех действий: **39 scheduled / 39 ready / 4 published** (не изменились), 0 ERROR/Traceback в journal за 10 мин.

## 5. Residual risks (честно, без прикрас)

1. **Два тестовых ролика остались на YouTube-канале** (`watch?v=5JeLhbun98k`, `watch?v=6HW23NkJMrg`): `delete` в Postiz убирает запись, но не само видео на платформе. Удаляются вручную в YouTube Studio (или через YT API с OAuth). На боевую сетку не влияют.
2. **P0.6 XSS**: закрыты все вставки, которые я нашёл обходом (`esc()` — 37 мест). Автоматической гарантии (статический линтер «нет сырых вставок в innerHTML») нет — это ручная проверка, возможны новые места при будущих правках UI.
3. **CSP** по-прежнему с `'unsafe-inline'` (инлайн-скрипт панели) — TODO оставлен в коде; XSS-риск снижен `esc()`, но не устранён организационно.
4. **P1.5**: рестарт оркестратора при смене `WEBAPP_PUBLIC_URL` всё ещё выполняется (процесс читает env один раз), но теперь — только при реальной смене значения (проверка `/proc/<pid>/environ`).
5. **P1.10** (проверка ответа Bot API + 429) и **P2.7** (метрики) проверены юнит-тестами/кодом, но **не наблюдались в живом инциденте** (не форсировали 429 в проде).
6. **P1.3 авто-очистка**: юнит-тест зелёный; в живом цикле сработает в течение ≤1 часа после 24-часового TTL — на момент отчёта таких постов нет.
7. **initData freshness (P0.5)**: панель, открытая со старым initData (>24ч), получит 401 — нужно переоткрыть из бота (это цель фикса, но поведение не «прогоняли» вживую из-за отсутствия старой сессии).
8. **Миграция v13 живьём** проверена только на текущей БД (перенос pending не затронул никого: активных backlog-pending в момент миграции не было). Откат схемы не предусмотрен (только вперёд) — как и раньше.
9. **P2.8**: единый лимит Telegram-медиа = «сжатие по `media.telegram_max_mb`» (0 = выключено). Для media-публикаций в Telegram файлы >50 МБ всё ещё будут падать с 413 — теперь это ловится заранее только в тест-контуре (400); боевой путь Telegram у нас link-only, поэтому не блокер.
10. Аудит-пункты, оказавшиеся **не дефектами** (проверено кодом/тестами): P0.3 (orphan API уже был), N4 (callback backlog резолвится), N6 (n8n-заглушки ожидаемы), N7 (broker — норма).

## 6. Как включить/выключить test_publish

- Выключатель: `test_publish.enabled: false` в `config.yaml` (API/UI вернут 403) — деплой/рестарт.
- Тест-каналы: `test_publish.test_integration_ids` (fail-closed: пусто = запрет). При переходе на боевые каналы — либо выключить контур, либо вписать боевые id в `prod_integration_ids` и осознанно поставить `allow_prod_channel: true`.
- TTL: `test_publish.cleanup_after_hours` (по умолчанию 24).
- UI: Actions → «Проверка (тестовый пост)»; API: `POST /webapp/api/test/schedule`; CLI: `--test-schedule --test-platform P --test-entity TYPE:ID`.

## 7. Артефакты

- Коммит `66b2050` (запушен в `master`), версия 8.2.1, WEBAPP_BUILD=815.
- Тесты: 304 (SSRF 22, миграции 4, P0/P1/P2 — остальное в существующих файлах).
- Ключевые файлы: `src/orchestrator/{webapp_api,test_publish,postiz_http,db,backlog,tail,scheduler,telegram_bot,safety,http_server,watcher,main,runner,status_sync,overflow,config}.py`, `webapp/app.js`, `scripts/{cloudflared_url_sync.sh,mcp_server.py}`, `tests/{test_ssrf_pin,test_p0_residual,test_migrations,test_test_publish}.py`, `.github/workflows/ci.yml`.
