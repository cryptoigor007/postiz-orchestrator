# Отчёт полной приёмки (код + WebApp все действия + CORS)

Дата: 2026-09-21 · Исполнитель: opencode · MODE: **local/stage (все мутации) + prod read-only + GUI против прода**

## Meta
| Параметр | Значение |
|---|---|
| Версия | `8.1.2` |
| UI-сборка | `813` (`/webapp/b/813/`) |
| Схема БД | `12` (+ `idx_eps_postiz_id_unique`) |
| Коммит (на момент прогона) | `eb6b37e` (после фикса read-only: `379552d`) |
| Python / node | venv 3.12.2 / node v26.7.0 |
| Длительность прогона | ~55 минут |
| Stage | `http://127.0.0.1:8081/8082/8083` (temp-БД, dry-run) |
| Prod | `https://entered-wildlife-profiles-directories.trycloudflare.com` (ключ из `/opt/orchestrator/.env`) |

## Авто
| Проверка | Результат |
|---|---|
| `ruff check src scripts tests` | **0 ошибок** PASS |
| `compileall src scripts` | PASS |
| `node --check webapp/app.js` | PASS |
| `pytest tests/ -q` | **235 passed** PASS |
| `./scripts/check.sh` | **ALL CHECKS PASSED** |
| `gui_check.sh` против stage | **GUI-ПРОВЕРКА ПРОЙДЕНА** |
| `gui_check.sh` против **прод** | **GUI-ПРОВЕРКА ПРОЙДЕНА** |

## CORS
| Кейс | Результат | Заголовки |
|---|---|---|
| PROD preflight (CORS выкл), `Origin: https://evil.example` | **PASS** | `HTTP/2 204`, `Access-Control-Allow-*` **отсутствуют** (ok для same-origin WebApp) |
| PROD GET `/webapp/b/813/` c `Origin: attacker.tld` | **PASS** | `HTTP/2 200`, ACAO нет |
| STAGE preflight (CORS вкл `ORCH_CORS_ORIGIN=https://panel.example`) | **PASS** | `204`; `ACAO: https://panel.example`; `Allow-Headers: Content-Type, X-Webapp-Key, X-Health-Token, Authorization`; `Allow-Methods: GET, POST, OPTIONS` |
| STAGE preflight с `Origin: attacker.tld` | **PASS** | ACAO остаётся сконфигурированным (`panel.example`), **origin атакующего не отражается** |
| Preflight не 500 | PASS | 204/200 |
| Минор (не CORS) | — | `HEAD` → **501** (нет `do_HEAD`); для браузеров ок, но CDN/health-пробы с HEAD будут получать 501 |

## WebApp: кнопки/действия (карта UI → API)
Из `webapp/app.js` извлечены **54 UI-действия** (`data-act`); каждому сопоставлен эндпоинт. Прогон:

| Слой | Метод | Итог |
|---|---|---|
| Auth-матрица | GET/POST | без ключа **401** ✓; неверный ключ **401** ✓; верный **200** ✓ |
| GET-эндпоинты (stage) | 17 запросов | **17/17 PASS (200)** |
| POST-эндпоинты (stage, dry-run) | 22 запроса | **22/22 PASS** (валидационные кейсы — ожидаемые 4xx: `queue/remove(bad)`, `force_link(bad)`, `cover/upload(bad)`, `cover/fetch(bad)`, `cover/frames(none)` → 400) |
| GET-эндпоинты (PROD, read-only) | 17 запросов | **17/17 PASS (200)** |
| READ-ONLY режим (`ORCH_READ_ONLY=1`) | 22 POST-запроса | после фикса — **все 403 `{error: read_only}`** ✓ (до фикса 13 маршрутов проходили) |

Ключевые действия (соответствие act → endpoint):
`schedule`→`POST /schedule` · `distribute`→`POST /distribute` · `scan-start[-dates]`→`POST /schedule` ·
`scan-restore`→`POST /queue/restore` · `backup`→`POST /backup` · `sync`→`POST /sync` · `reconcile`→`POST /reconcile` ·
`pause-all`/`resume-all`→`POST /pause`/`/resume` · `pause-one`/`resume-one`→`POST /pause_platform`/`/resume_platform` ·
`toggle-mode`→`POST /scheduling_mode` · `tail-on`/`tail-off`→`POST /series_end` · `backlog-answer`→`POST /backlog/answer` ·
`folder-*`→`POST /roots`, `GET /browse[/search]` · `queue-edit-save`→`POST /queue/edit` · `queue-remove[-everywhere|-film-only]`→`POST /queue/remove` ·
`queue-restore-all`→`POST /queue/restore` · `queue-cleanup-orphans`→`POST /queue/cleanup_orphans` ·
`cover-pick`→`GET /cover/list|/cover/thumb`, `POST /cover/upload|/cover/fetch|/cover/frames` ·
`manual-*`→`POST /manual/scan`, `/manual/uploads/<id>/{confirm,reject,ignore,claim-action,claim-mark}` ·
`sched-save|sched-reset`→`POST /schedule_settings` · `group-add|group-remove`→`POST /groups` ·
`job-cancel`→`POST /job/cancel` · `force-link`→`POST /force_link` · `refresh`→`GET /status` (reload вида).

Побочные эффекты: все мутации выполнялись на **stage с dry-run** (публикаций не создавалось);
прод — только чтение (17 GET) + reconcile не запускался.

## Security / logic (spot-check)
| ID | Тема | Результат |
|---|---|---|
| S-browse | Нет fallback `/` при невалидном корне | **PASS** (в коде отсутствует; тесты `test_webapp_roots`) |
| S-broker | Запрет traversal, whitelist SQL | **PASS** (`test_broker_allowlist`, `test_residual_closure`) |
| R1' | Publishing reserve; create-fail → `error` (без «грязного» сохранения) | **PASS** (`test_closure_8_1`) |
| R2/R7 | Ограниченные кэши (watcher/media) | **PASS** (тесты) |
| L14 | `posts_today` сбрасывается по календарному дню TZ | **PASS** (тест) |
| L30 | `exception_days` учитываются в safety | **PASS** (тесты) |
| S18 | `/metrics` и `/health` без секретов | **PASS** (живой payload прод проверен: token/secret отсутствуют) |
| S18b | Health bind | **PASS** (`ORCH_HTTP_BIND=0.0.0.0` на проде для LAN; дефолт 8.1.2 — `127.0.0.1`) |
| R3 | UNIQUE `postiz_post_id` (schema v12) | **PASS** (индекс создан на проде) |
| D6 | Watcher не падает на недоступной папке | **PASS** (hardening + тест; в проде 0 `PermissionError` за 30 мин) |
| D7 | `cloudflared_url_sync` fallback URL | **PASS** (меню-кнопка обновлена) |
| **R13** | **READ-ONLY блокирует все мутации** | **НАЙДЕН ДЕФЕКТ → ИСПРАВЛЕН**: до фикса проходили `distribute, sync, reconcile, backup, scheduling_mode, pause_platform, resume_platform, queue/restore, queue/cleanup_orphans, queue/edit, queue/remove, series_end, manual/scan, roots` (200). Теперь **любой POST → 403** + тест `test_read_only_blocks_all_mutations` (235-й тест) |
| D1–D5, D8 | Ранее исправленные дефекты инструментария (ruff, backup, main, check.mjs, gui_check.sh, publishing UI, build-id тест) | **PASS** (см. `docs/REPORT-8.1.2-ADOPTION.md`) |

## Блокеры
1. Нет блокирующих. Единственный минор — `HEAD` → 501 (рекомендация в апстрим: реализовать `do_HEAD`).

## Не проверялось
- Ручной клик-обход глазами в Telegram (компенсировано jsdom-проверкой всех экранов + API-эквивалентами действий).
- Реальная публикация вне расписания на бою (18:00 МСК — по плану; 12:00/12:16 уже подтверждены живыми).
- Полная побайтовая сверка SSD (отдельная задача, вне рамок приёмки).

## Вердикт
**МОЖНО В ПРОД** — 8.1.2 работает на сервере, авто+GUI+CORS+все действия — PASS; найденный дефект read-only исправлен и задеплоен.

Следующие шаги (≤5):
1. Слить фикс read-only в `master` и деплой (сделано: `379552d`, задеплоено).
2. В апстрим: `do_HEAD`; вынести список мутаций из read-only (полный запрет POST); см. `docs/REPORT-8.1.2-ADOPTION.md`.
3. 18:00 МСК — контроль публикации шорта 305 + Telegram-ссылки (18:15).
4. При подключённом SSD — полная побайтовая сверка (`scripts/ssd_copy_verify.sh` + `rsync -c`).
5. По желанию: MCP-серверы / Telegram↔opencode bridge.


---

# ЧАСТЬ 2 — «Жёсткий» прогон (fault-injection, безопасность, миграции, отказоустойчивость)

Дата: 2026-09-21 (продолжение). MODE: local/stage (мутации и инъекции), prod read-only.

## 2.1 Fault injection клиента Postiz (`/tmp/fault_inject.py`, стабы на 127.0.0.1)
| Кейс | Ожидание | Результат |
|---|---|---|
| Мёртвый порт (ConnectError) | безопасные повторы (3 попытки), затем ошибка | **PASS** — ConnectError за ~9 с, 3 попытки |
| Висящий сокет (ReadTimeout) | **1 POST без повтора** (защита от дубликата) | **PASS** — POST-запросов = 1 |
| 429 на первой попытке | безопасный повтор → ровно 1 пост | **PASS** — 2 запроса, `post-2` создан один раз (после фикса, см. 2.2) |
| 5xx на POST | **без повтора** (возможен дубликат) | **PASS** — POST-запросов = 1 |
| GET на 5xx | повтор (идемпотентно) | **PASS** — 3 GET-запроса (проверено отдельным прогоном) |

## 2.2 Найденные в жёстком прогоне дефекты и фиксы (задеплоено, коммит `37a659e`)
| ID | Дефект | Фикс |
|---|---|---|
| **H1 (security)** | `POST /cover/fetch` позволял **SSRF**: успешно инициировал запросы к `http://127.0.0.1:…` и `http://169.254.169.254/…` (metadata), а также мог следовать redirect на приватный адрес | добавлена проверка хоста: все резолвы должны быть публичными (блок private/loopback/link-local/reserved/multicast/unspecified); redirect-хопы валидируются (до 3); ответы только-картинки. Тесты: `test_host_is_public_blocks_private`, `test_cover_fetch_blocks_private_urls`. Live: все приватные URL → `400 {"error": "url host not allowed (private/loopback)"}` |
| **H2 (reliability)** | **429 не повторялся** (обрабатывался вне retry-хелпера) → лимит Postiz «съедал» попытку поста | 429 теперь ретраится внутри хелпера (для POST безопасно: ресурс не создан). Тесты: `test_post_429_is_retried`, `test_post_500_is_not_retried` |
| **H3 (reliability)** | `list_scheduled` не использовал retry (одиночный GET) | прогоняется через `_request_with_retry` (чтение идемпотентно) |

## 2.3 Миграции БД (батарея 4) — 4/4 PASS
| Кейс | Результат |
|---|---|
| Свежая БД → v12 + 3 индекса | **PASS** |
| v11 → v12 (миграция на копии прод-схемы) | **PASS** (unique-индекс создан) |
| БД с **дубликатами `postiz_post_id`** → не падает | **PASS** (индекс пропущен graceful, сервис поднимается) |
| Повторная инициализация v12 (идемпотентность) | **PASS** |

## 2.4 Отказоустойчивость GUI (батарея 5) — **ПРОЙДЕНА**
Скрипты: `tests/gui/check_failures.mjs` + `scripts/gui_check_failures.sh`.
| Кейс | Результат |
|---|---|
| Все API отвечают 500 | **10/10 экранов показывают ошибку**, не «белый экран» |
| Зависание спиннера | **нет** (busy overlay скрыт) |
| Необработанные JS-ошибки | нет |
| Восстановление API → «Обновить» | UI снова рендерится |

## 2.5 Конкурентность/нагрузка (батарея 2)
| Кейс | Результат |
|---|---|
| 30 параллельных GET `/status` | **30/30 = 200** (SQLite per-op соединения + WAL, без 500/блокировок) |
| 11 параллельных GET разных эндпоинтов | **11/11 = 200** |
| 5 параллельных POST `/schedule` | повторные не ломают lock (детерминированно покрыто `test_schedule_endpoint_single_flight`); live — последовательные запуски после быстрого завершения предыдущего |

## 2.6 Обход путей и инъекции (батарея 1)
| Кейс | Результат |
|---|---|
| `browse?path=/`, `/etc`, `/root`, `../..`, URL-encoded traversal | **PASS** — всё прижимается к разрешённому корню (листинг `/` невозможен) |
| `cover/thumb?path=/etc/passwd`, traversal | **PASS** — 404 |
| `cover/fetch` `file://`, `ftp://` | **PASS** — 400 (только http/https) |
| `cover/fetch` на приватные адреса | **PASS** после фикса H1 — 400 |
| SQL-инъекция (`'); DROP TABLE shorts;--`) в `queue/edit` | **PASS** — параметризованные запросы, таблица цела |

## 2.7 Итог жёсткого прогона
Найдено и исправлено **3 дефекта** (1 security — SSRF, 2 reliability — 429/list retry), миграции и
отказоустойчивость — PASS. Тестов стало **239** (было 235). Всё задеплоено на прод (`37a659e`).

**Обновлённый вердикт: МОЖНО В ПРОД (жёсткий прогон пройден).**
