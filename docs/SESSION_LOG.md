# SESSION LOG

## 2026-09-19 — Plan 1: Engines core + data model
- docs: TZ (spec) + Plan 1 (`docs/superpowers/`).
- Task 1: `platform_uploads` registry + upsert/confirm (schema v9). Tests: `tests/test_uploads_db.py` (3).
- Task 2: `config.engines` + `engine_for()`; `config.yaml` engines. Tests: `tests/test_engines_config.py` (1).
- Task 3: engines base (`Destination`, `PublishResult`) + capability registry. Tests: `tests/test_engines_registry.py` (3).
- Task 4: `PostizEngine` adapter (no regressions). Tests: `tests/test_postiz_engine.py` (2).
- Full suite: 85 passed.
- Commits: TZ/plan, db registry, config engines, engines base, postiz adapter.

### Next (not started)
- Plan 2: `direct:youtube` (list/update/delete/claims) + manual uploads scan/match/confirm.
- Plan 3: UI/API/MCP + placement.
- Plan 4: n8n. Plan 5: browser (experimental).

## 2026-09-19 — Plan 2 (начало)
- direct youtube engine (list/update/delete/claims) + tests (3) → commit f55ac2a.
- matching score (title/date/duration) + tests (4) → commit 7df4fac.
- Full suite: 92 passed.
- Next: token broker (доступ к OAuth-токену YouTube из Postiz), scan/confirm service, UI/API/MCP.
- token broker: client + server + unit (commit), установлен на VM 120, `token-broker.service` active.
  - health 200; чужой секрет 401; `platform=youtube` → 404 (канал ещё не подключён) — корректно.
  - `.env` оркестратора: TOKEN_BROKER_URL/SECRET.
  - Доступен с Mac и с pve.
- Предусловие для реального YouTube: подключить YouTube-канал в Postiz.

## 2026-09-19 — Plans 2/3 (ядро фичи)
- manual service scan/confirm/reject (tests) → commit.
- webapp `/manual/*` API (plan/uploads/scan/confirm/reassign/reject/ignore/claim-action) + tests.
- UI раздел «Manual» (scan/confirm/reject/ignore/клеймы), i18n RU/EN, nav.
- engines n8n + browser(experimental), source factory (only enabled platforms), wired in build.
- Deploy: rsync + restart; проверено: health ok, manual/plan platforms=[telegram,youtube], scan youtube → 404 (нет подключённого канала).
- Tests: 103 passed.
- Prerequisite live YouTube: подключить YouTube-канал в Postiz (broker отдаёт токен).

## 2026-09-19 — Глубокий аудит
- Static: compileall ok, node --check ok, tests 105 passed.
- Server (pve): orchestrator active; DB schema v9 + platform_uploads; manual plan/scan ok; ошибок в логе нет.
- VM: token-broker active; cloudflared active; sync timer active. UI b21 рендерится (manual view).
- Security: секретов в трекнутых файлах нет; .env игнорируется.
- Исправлено в ходе аудита:
  1) scan пропускает движки без `list`;
  2) confirm/reassign → 409 при конфликте привязки;
  3) брокер-клиент даёт понятную ошибку (`token broker: …`);
  4) удалён мёртвый код (health.py, calendar_view.py) + чистка тестов.
- Открытые риски: YouTube не подключён; клеймы через API ограничены; browser — экспериментальный; n8n требует N8N_URL.

## 2026-09-19 — Самостоятельные доработки (после аудита)
- config: секция `manual_uploads` (лимиты/порог/расписание).
- runner: ежедневный скан ручных загрузок (`scan_all`), пишет `manual_last_scan`.
- security: IP-allowlist у токен-брокера (только pve/localhost), rate-limit webapp API (env `WEBAPP_RATE_LIMIT`).
- tooling: ruff-конфиг, авто-фиксы (линт чист), `scripts/check.sh` + `.githooks/pre-commit`.
- i18n: справка по разделу «Ручные»; сборка b22.
- Tests: 110 passed. Деплой: rsync --delete (IDENTICAL) + restart, все сервисы active.

## 2026-09-19 — Полный обзор + README
- Проверено всё: 110 тестов, линт чист, сервисы active (orchestrator, cloudflared, sync-timer,
  watchdog, token-broker), health ok, manual API отвечает.
- Написан подробный README.md (архитектура, пайплайн, конфиг, движки, ручные загрузки, MCP,
  Telegram, деплой, эксплуатация, диагностика, БД, ограничения).

## 2026-09-19 — Полнота WebApp
- Выведены реализованные, но отсутствовавшие в UI функции: sync, reconcile, backup, schedule
  (кнопки в «Действия»), пауза на платформу (в «Платформы»), динамический список платформ
  в «Обновить ссылку», ручная пометка клейма (раздел «Ручные»).
- Menu-button sync-скрипт сделал авто-версионным (BUILD читается из кода) — устранён дрейф
  версии; скрипт добавлен в репозиторий (deploy/cloudflared_url_sync.sh).
- Tests: 112 passed; lint чист. Сборка b24 задеплоена (menu → b24).

## 2026-09-19 — Проверки и прикрутка
- scan: учёт `lookback_days` и `page_size` из конфига (окно поиска, размер страницы).
- MCP: добавлены инструменты sync/reconcile/backup/schedule/pause_platform (+ тесты).
- Полный чеклист проверки: docs/VERIFICATION.md.
- Telegram: очищена история сообщений бота (18 удалено), отправлено одно чистое.
- Tests: 115 passed; lint чист.
