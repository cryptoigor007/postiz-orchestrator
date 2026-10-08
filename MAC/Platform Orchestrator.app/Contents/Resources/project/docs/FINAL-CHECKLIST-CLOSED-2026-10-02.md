# PLATFORM ORCHESTRATOR 8.6.0 — FINAL RESIDUAL CHECKLIST

Дата: 2026-10-02
Источник: `PLATFORM-ORCHESTRATOR-8.6.0-REMAINING-ISSUES.txt`

## CP00 — исходный residual

- [DONE] Канонический residual V-01…V-26 зафиксирован в `checkpoints/REMAINING-ISSUES-SOURCE.txt`.
- [DONE] Исходный архив SHA256 сохранён в `checkpoints/BASELINE_SHA256.txt`.
- [DONE] Предварительный rollback snapshot: `PO-8.6.0-CHECKPOINT-01-PRE-FIX.tar.gz`.

## CP01 — baseline

- [DONE] Baseline targeted residual suite: 77 passed.
- [DONE] Baseline full pytest: 961 passed / 5 skipped / 0 failed.
- [DONE] Baseline runtime AST scan: 0 `except: pass` в runtime.

## CP02 — P1 correctness/security

- [DONE] V-12: reconciliation error taxonomy отделена от `missing_on_platform`; AUTH/TRANSIENT/network-class failures не наращивают missing streak.
- [DONE] V-19: `media_transfer.fetch_url` использует pinned-IP после authoritative DNS validation; SSRF regression покрыт тестами.
- [DONE] V-07: `next_retry_at` future не claim'ится; отдельная regression проверка присутствует.
- [DONE] V-13: provider `list_remote*`/`list_scheduled*` exception paths логируют warning/error/exception; final audit: `unlogged=0`.
- [DONE] V-04: runtime bare-except-pass = 0.

Rollback checkpoint: `PO-8.6.0-CHECKPOINT-02-TARGETED-FIXED.tar.gz`.

## CP03 — multi-account

- [DONE] V-05/V-16: safety state account-scoped; неоднозначный scope fail-closed.
- [DONE] V-20: backlog state/callbacks account-scoped; automatic runner cycle теперь также перебирает известные `account_id` отдельно.
- [DONE] V-21: manual-upload occupancy scoped by `account_id`; ambiguous scope fail-closed.
- [DONE] V-06: global restore-all требует явного `confirm_all`; backend audit log + UI confirmation.
- [DONE] V-09: Instagram finalize account-scoped при SELECT/UPDATE.
- [DONE] V-17: webapp rate limiting хранится в SQLite, не в памяти worker'а.

Rollback checkpoint: `PO-8.6.0-CHECKPOINT-03-BRANCH-GUI-FIXES.tar.gz`.

## CP04 — branch regressions / additional defects

Добавлен `tests/test_residual_v4.py` и исправлены дополнительные runtime-дефекты, найденные во время аудита:

- [DONE] Scheduler `_backlog_active`: исправлены SQL parameters для account scope.
- [DONE] `BacklogManager.missed_default/should_remind/mark_reminded/auto_default`: устранены undefined `account_id` paths.
- [DONE] `BacklogManager.ask`: notifier теперь получает точный `account_id`.
- [DONE] Telegram backlog callbacks/commands несут account scope.
- [DONE] Runner backlog cycle обрабатывает несколько аккаунтов одной platform независимо.
- [DONE] Deferred provider-circuit branch сохраняет `next_retry_at` и publish-attempt metadata.
- [DONE] Webhook DLQ/dead branch покрыт отдельным regression.
- [DONE] GUI smoke script проверяет фактическую установку `jsdom`, а не только наличие каталога.

## CP05 — automated final verification

- [DONE] Full pytest: **968 passed / 5 skipped / 0 failed**.
- [DONE] `scripts/final_audit.py`: **RC=0**, `FINAL AUDIT: ALL AUTOMATED CHECKS PASSED`.
- [DONE] Capability audit: 42 modules / 0 errors.
- [DONE] Provider catalog/manifests: 42 / 42.
- [DONE] Runtime Python parse/compile: 169 source modules.
- [DONE] Runtime bare-except-pass: 0.
- [DONE] Active secret/query-key scan: 0.
- [DONE] Owner-specific active IP scan: 0.
- [DONE] Provider list observability: 0 unlogged exceptions.
- [DONE] CI pins: pytest 8.3.5 + pytest-asyncio 0.25.3 exact in requirements/lock/CI.
- [DONE] Shell syntax: OK.

### Coverage

Текущий воспроизводимый запуск с `coverage run --branch --source=src`:

- statements: 68.6009%
- branches: 52.0594%
- combined coverage reported by Coverage.py: 64.2830%
- statements: 17,733
- branches: 6,264
- covered branches: 3,261

Это не заявляется как 100% branch coverage. Residual V-03 трактовался по исходному чек-листу как необходимость закрыть конкретные deferred/next_retry, webhook DLQ, multi-account UI/backlog и restore-all ветки; эти regression tests проходят.

## CP06 — GUI environment

- [DONE] JS syntax/static UI wiring checks.
- [DONE] `scripts/ci_gui_smoke.sh` теперь fail-safe проверяет `node_modules/jsdom/package.json` и при необходимости пытается восстановить зависимости через `npm ci`/`npm install`.
- [BLOCKED-ENV] Полный локальный browser-like GUI smoke в текущем sandbox не выполнялся: рабочая среда не имеет доступного установленного `jsdom` и локальный npm cache пуст. Код проверки исправлен; это ограничение среды, а не тестируемого Python/JS runtime.

## Canary

- [DONE] Static+dry canary: **42/42 modules**.
- [DONE] Targeted dry canary: YouTube / Telegram / Facebook = 3/3 `dry_ready`.
- [INFO] Live write не выполнялся автоматически.

## Внешний остаток

### V-01 — LIVE canary

- [EXTERNAL] Реальный canary на владельческих YouTube + Telegram + Meta/TikTok аккаунтах требует действующие аккаунты, токены и provider-side permissions. Эти данные отсутствуют в sandbox.

### V-02 — App Review / Advanced Access / WABA / TikTok audit / credentials

- [EXTERNAL] Эти операции выполняются во внешних кабинетах/аккаунтах и не могут быть честно закрыты изменением архивного кода.

## INFO, не баги

V-10 audit-only `publish.completed`, V-11 provider semantics, V-14 explicit live opt-in, V-15 token path/tg voice quoting, V-18 schema/pre-migration backup, V-22/V-23/V-24/V-25 и V-26 остаются как зафиксированные архитектурные/операционные решения.

## Финальный verdict

Все исполнимые внутри архива **кодовые, security, multi-account, regression и CI** пункты residual закрыты и защищены автоматическими проверками. Неисполненными остаются только внешние V-01/V-02 и sandbox-only GUI smoke limitation. Архив не помечается как live-canary verified.
