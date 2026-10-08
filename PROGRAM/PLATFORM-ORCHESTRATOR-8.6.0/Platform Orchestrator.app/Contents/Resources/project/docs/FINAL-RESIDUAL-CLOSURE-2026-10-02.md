# PLATFORM ORCHESTRATOR 8.6.0 — FINAL RESIDUAL CLOSURE

Дата: 2026-10-02

## Итог

Архивный residual закрыт по всем пунктам, которые можно выполнить внутри кода, тестов, CI и локального dry-canary. В ходе проверки обнаружены и исправлены дополнительные runtime-дефекты, не перечисленные в исходном residual.

Итоговая автоматическая проверка:

- Full pytest: **968 passed / 5 skipped / 0 failed**.
- `scripts/final_audit.py`: **RC=0**; `FINAL AUDIT: ALL AUTOMATED CHECKS PASSED`.
- Capability audit: **42 modules / 0 errors**.
- Provider catalog/manifests: **42 / 42**.
- Runtime parse/compile: **169 source modules**.
- Runtime bare `except: pass`: **0**.
- Active secret/query-key scan: **0**.
- Owner-specific active IP scan: **0**.
- Provider-list unlogged exception paths: **0**.
- Dependency pins: pytest **8.3.5**, pytest-asyncio **0.25.3**.
- Static+dry canary: **42/42**.
- Targeted dry canary YT/TG/Facebook: **3/3 dry_ready**.

## Исправления по исходному residual

### V-12 — reconciliation taxonomy

Исправление оставляет provider/network/auth/error состояния в error taxonomy и не превращает ошибку получения статуса в `missing_on_platform`. Regression tests проверяют `AUTH_EXPIRED`/`FATAL` и отсутствие ложного missing streak.

### V-19 — SSRF pinning

`media_transfer.fetch_url` использует authoritative DNS resolution и подключение к проверенному pinned IP вместо повторного обычного DNS resolve. SSRF regression находится в отдельном тестовом наборе.

### V-03 / V-07 — branch regressions / retry

Добавлены явные regression paths для deferred provider circuit с `next_retry_at`, webhook DLQ/dead path, multi-account UI/backlog и restore-all confirmation. Future `next_retry_at` отдельно проверяется как неclaimable.

### V-04 / V-13 — exception observability

Runtime `except ...: pass` доведён до нуля. Provider list exception paths логируют ошибку и сохраняют observability; final audit подтверждает `provider list exception logging=0 unlogged`.

### V-05 / V-16 — safety account scope

Safety state использует account-scoped таблицу и fail-closed semantics при неоднозначном account scope.

### V-20 — backlog account scope

Backlog state/callbacks работают по `(platform, account_id)`. Дополнительно найдено и исправлено несколько runtime-проблем:

1. Scheduler `_backlog_active` передавал неверное количество SQL parameters.
2. `BacklogManager.missed_default`, `should_remind`, `mark_reminded` и `auto_default` имели пути с undefined local `account_id`.
3. `BacklogManager.ask` не передавал account id notifier'у.
4. Telegram `/backlog_*` callbacks получили explicit account scope.
5. Runner backlog cycle теперь обнаруживает известные account ids и обрабатывает каждый account отдельно.

### V-21 — manual uploads

Occupancy/matching checks используют account scope; ambiguous multi-account lookup завершается fail-closed.

### V-06 — restore-all

Global restore-all требует явного `confirm_all`, backend пишет audit entry, UI показывает отдельное подтверждение.

### V-09 — Instagram finalize

SELECT/UPDATE paths защищены account scope; неоднозначный account id не выбирается молча.

### V-17 — webapp rate limit

Rate-limit state хранится в SQLite, что не зависит от памяти отдельного worker process.

### V-08 — dependency lock

Exact pytest/test-runner pins подтверждены final audit в requirements, lock и CI.

## Дополнительное исправление GUI smoke

`ci_gui_smoke.sh` больше не считает пустой каталог `node_modules` корректной установкой. Проверяется фактический `node_modules/jsdom/package.json`; при отсутствии выполняется попытка `npm ci` с fallback на `npm install`.

Сам browser-like smoke не был выполнен в текущем sandbox: `jsdom` отсутствует, а локальный npm cache/network недоступны. Это ограничение среды выполнения. Статические JS/UI wiring checks проходят.

## Coverage

Команда:

`COVERAGE_FILE=/tmp/po_cov_final coverage run --branch --source=src -m pytest -q`

Результат:

- Statements: **68.6009%** (12,165 / 17,733).
- Branches: **52.0594%** (3,261 / 6,264).
- Combined Coverage.py: **64.2830%**.

Full branch coverage не заявляется. Для residual V-03 закрыты именно перечисленные в backlog ветки.

## Canary status

Static + dry canary завершён по всем 42 provider modules. Реальный live write не запускался автоматически.

YouTube / Telegram / Facebook дают `dry_ready`; Telegram в dry режиме сообщает отсутствие реального bot token/config, что ожидаемо для sandbox.

## Что остаётся за пределами архива

**V-01:** реальный canary на владельческих аккаунтах YouTube + Telegram + Meta/TikTok. Для этого нужны реальные account credentials, tokens, provider permissions и разрешение владельца на фактическую публикацию/очистку.

**V-02:** App Review / Advanced Access / WABA / TikTok audit / credentials. Это операции во внешних кабинетах и не могут быть честно закрыты кодом архива.

Поэтому архив не маркируется как подтверждённый реальный LIVE-canary release.

## Checkpoints

- CP00 baseline: `checkpoints/CHECKPOINT-00-BASELINE.txt` + исходный SHA256.
- CP01 pre-fix rollback: `/mnt/data/PO-8.6.0-CHECKPOINT-01-PRE-FIX.tar.gz`.
- CP02 targeted fixed: `/mnt/data/PO-8.6.0-CHECKPOINT-02-TARGETED-FIXED.tar.gz`.
- CP03 branch/gui: `/mnt/data/PO-8.6.0-CHECKPOINT-03-BRANCH-GUI-FIXES.tar.gz`.
- CP04 final verified: `/mnt/data/PO-8.6.0-CHECKPOINT-04-FINAL-VERIFIED.tar.gz`.

## Final release files

Release archive: `PLATFORM-ORCHESTRATOR-8.6.0-FINAL-FIXED-2026-10-02.zip`.

После сборки archive SHA256 записывается рядом в `.sha256` file.
