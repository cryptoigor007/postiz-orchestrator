# Orchestrator

Пайплайн публикаций: **VideoMaker + ShortsMaker → Orchestrator (module path) → соцсети**, с веб-панелью (Telegram
WebApp), Telegram-ботом, MCP-интеграцией для ИИ и модулем распознавания ручных загрузок.

Версия: `8.6.0` HARD_CUT (module path), gate: `scripts/gate_platform_zero.sh`.

> **One-click:** macOS — двойной клик `Platform Orchestrator.app` или `START.command`; Linux — `./start.sh`; Windows — `start.bat`.  
> Контекст сессий: `docs/HANDOFF.md`

---

## 1. Что есть в системе (общая картина)

```
VideoMaker/ShortsMaker  ──►  Orchestrator (Python, module path)  ──►  соцсети
   (папки с видео)             watcher→scheduler→publisher        (modules)     (Telegram, YouTube, …)
                                        │
                    ┌───────────────────┼────────────────────────┐
                    ▼                   ▼                        ▼
              SQLite (data.sqlite)  Telegram-бот (команды)   WebApp (панель)
                                        │                        │
                                        └──── MCP ──► ИИ-клиенты (opencode/Claude) ──► engines
```

Компоненты:

| Компонент | Где | Что делает |
|---|---|---|
| **Orchestrator** | PVE-хост `pve`, systemd | сканирует папки, планирует, публикует через platform modules, синхронизирует статусы |
| **WebApp** | HTTP `:8080` на `pve` | панель управления (10 разделов), доступ через Telegram Menu Button |
| **Telegram-бот** | orchestrator bot | команды + claims A3 + backlog |
| **Platform modules** | in-process | **42 provider modules**: publishing, messaging, community, CMS, newsletter, business and protocol integrations |
| **Token store** | `tokens/*.json` + optional broker | OAuth tokens local |
| **Cloudflare tunnel** | `pve` | публичный HTTPS на webapp (временный URL) |
| **MCP-серверы** | на машине ИИ-клиента | инструменты оркестратора для ИИ |

---

## 2. Структура репозитория

```
src/orchestrator/
  main.py            вход (CLI, сборка компонентов)
  runner.py          главный цикл (watch/sync/recon/backup/manual-scan)
  watcher.py         сканирование папок VideoMaker/ShortsMaker
  scheduler.py       раскладка по слотам (long/thematic/standalone shorts)
  slots.py           расчёт слотов, jitter, интервалы
  safety.py          лимиты, warmup, min_interval, паузы, классификация ошибок
  publisher.py       публикация сущности на платформу (upload→create), идемпотентность
  status_sync.py     синхронизация статусов + реконсиляция
  link_updater.py    подстановка ссылки на длинное видео в шортсы
  tail.py            режим «хвоста» серии
  overflow.py        перенос лишних шортсов в shorts_overflow
  backup.py          бэкап SQLite (Connection.backup; sqlite_backup)
  metrics.py         счётчики рантайма
  manual_uploads.py  распознавание/сопоставление ручных загрузок
  manual_sources.py  фабрика движков-источников (по платформам)
  webapp_api.py      API панели + отдача UI (self-contained страница)
  telegram_bot.py    команды/уведомления
  telegram_transport.py long-poll транспорт
  db.py              SQLite схема/миграции/доступ
  config.py          pydantic-конфиг (config.yaml)
  platforms/         нативные provider modules (publishing/messaging/webhooks)
  provider_supervisor.py  per-provider/account health + circuit breaker
  outbox.py          durable transactional outbox → jobs
  durable_jobs.py    SQLite-backed durable job state
  webhook_ingress.py webhook verification + event inbox
  consistency.py     remote/local consistency sweeper
  auth_tokens.py     единый account-scoped token path
scripts/
  check.sh               ruff + compileall + node --check + pytest
  mcp_server.py          MCP-сервер оркестратора (stdio)
  token_broker.py        брокер токенов (запускается на VM)
  telegram_opencode_bridge.py  мост Telegram ↔ opencode
webapp/              index.html, app.js, styles.css (i18n RU/EN)
deploy/              systemd-юниты и инструкции
docs/                спецификации, план, журнал, гайды
config.yaml          конфигурация поведения
```

---

## 2a. Структура папок с видео (поддерживаемые схемы)

Оркестратор видит **локальные пути на сервере** (pve). Если папка лежит на Mac —
её надо расшарить (SMB) и смонтировать на pve, либо скопировать на сервер.

Схема «платформенные подпапки» (рекомендуется, чтобы у каждой соцсети была своя
дорожка/версия и не было клеймов по музыке):

```
<корень>/
  <Серия>/
    youtube/    final.mp4        # версия для YouTube
    telegram/   final.mp4        # версия для Telegram
    instagram/  final.mp4        # и т.д. (имя папки = имя платформы из config.yaml)
    shorts/
      short_01/
        youtube.mp4              # версия шортса под платформу
        telegram.mp4
        cover.jpg                # необязательно
```

Поддерживается и старая схема VideoMaker:
```
<Серия>/wide/final_16x9.mp4
<Серия>/vertical/final_9x16.mp4
<Серия>/shorts/short_XX/*.mp4
```
ShortsMaker: корень с именем `shortsmaker*` (или маркер `.shortsmaker`) и `*.mp4` внутри.

Планировщик сам выбирает версию: если есть `<platform>/` — берёт её, иначе
`wide/vertical` (или `video_path` для шортсов).

## 3. Как это работает (пайплайн)

Главный цикл (`runner.py`) периодически запускает фазы:

1. **watch** (каждые `watcher_interval_sec`, 75с): `watcher.scan()` ищет новые видео
   (`<серия>/wide/final_16x9.mp4`, `<серия>/vertical/final_9x16.mp4`, `<серия>/shorts/*`),
   `scheduler` раскладывает по свободным слотам (`slots.py`), с учётом `safety`.
2. **sync** (`status_sync_interval_sec`, 180с): подтягивает статусы через module get_status
   (`scheduled → published`), обновляет `release_url`, подставляет ссылку в шортсы
   (`link_updater`), работает «хвост» (`tail`).
3. **recon** (раз в `reconciliation_interval_hours`, 24ч): сверка «наши ↔ platform remote» (ModuleReconciliation)
   (пропавшие/сироты).
4. **backup** (`interval_hours`, 6ч): `sqlite3 Connection.backup` в `backups/`, хранение `keep_days`; перед миграциями схемы — автобэкап `pre_migration_*.sqlite` (D11).
5. **manual scan** (`schedule_scan: daily`): поиск ручных загрузок в соцсетях (§7).

Публикация (`publisher.py`): идемпотентно (ключ `entity_type:entity_id:platform:время`),
upload медиа → module publish, запись статуса, jitter и лимиты.

Сущности БД: `long_videos`, `shorts`; статусы на платформу — `entity_platform_status`
(`status`, `external_id`, `external_sub_id`, `external_url`, `scheduled_for`, `source`, `release_url`, …; legacy_* columns — COALESCE read-only, no dual-write).

---

## 4. Конфигурация

### 4.1 `config.yaml` (поведение)

- `schedules` — расписание: `long_video` (вт/пт 16:00), `shorts_standalone`
  (пн/ср/чт/сб/вс в 12:00 и 18:00), `shorts_thematic` (default 20:30).
- `platforms` — каналы: `enabled`, `video_variant` (wide/vertical), `daily_limit`,
  `integration_id` (ID канала с платформы).
- `engines` — маршрут публикации: `module:youtube` / `module:telegram` / … (см. `config.example.yaml`); также manual_uploads (скан/list/claims). Основной `Publisher` — **module path only**.
- `manual_uploads` — параметры распознавания ручных загрузок (§7).
- `tail`, `limits`, `link_update`, `description_templates`, `safety`, `telegram`,
  `backup`, `timezone`, интервалы.

### 4.2 `.env` (секреты/адреса; git-ignored)

| Ключ | Назначение |
|---|---|
| `ORCH_PUBLIC_BASE_URL` | публичный URL WebApp / tunnel оркестратора |
| `TELEGRAM_BOT_TOKEN` | publisher-бот |
| `TELEGRAM_MODE=poll\|off` | long-poll команд |
| `WEBAPP_PUBLIC_URL` | публичный URL панели |
| `WEBAPP_ACCESS_KEY` | ключ доступа к панели |
| `WEBAPP_BROWSE_ROOT` | разрешённые корни обзора папок (через запятую) |
| `TOKEN_BROKER_URL`, `TOKEN_BROKER_SECRET` | доступ к брокеру токенов (опц.) |
| `ORCH_READ_ONLY` | `1` — блокирует publish creates |
| `ORCH_HTTP_BIND` | bind health/webapp (default `127.0.0.1`) |

OAuth / platform tokens: `tokens/<platform>__<account_id>.json` (chmod 600). Общий `tokens/<platform>.json` разрешается только явным single-account fallback flag.

---

## 5. Установка и запуск

### Локально (Mac/Linux)

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
PYTHONPATH=src ./venv/bin/python -m orchestrator.main --version
PYTHONPATH=src ./venv/bin/python -m orchestrator.main --config config.yaml \
    --db data/data.sqlite --daemon --health-port 8080
```

### Сервер (systemd, `pve`)

```bash
sudo useradd -r -s /usr/sbin/nologin orchestrator || true
sudo mkdir -p /opt/orchestrator/{data,backups,logs}
sudo rsync -a --delete --exclude venv --exclude .env ./ /opt/orchestrator/
sudo python3 -m venv /opt/orchestrator/venv
sudo /opt/orchestrator/venv/bin/pip install -r /opt/orchestrator/requirements.txt
sudo cp /opt/orchestrator/deploy/*.service /opt/orchestrator/deploy/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now orchestrator.service orchestrator-watchdog.timer
```

Проверка: `curl http://127.0.0.1:8080/health`.

---



### TLS / health (ops)
- Provider HTTP: TLS verify **on** by default; provider requests идут через shared `ModuleHttpClient`.
- Health HTTP bind: `ORCH_HTTP_BIND` (default `127.0.0.1`); metrics may require `ORCH_HEALTH_TOKEN`.
- `ORCH_READ_ONLY=1` blocks publish creates.

## 6. Provider modules и fault isolation

**HARD_CUT:** основной runtime publish/send path работает только через нативные modules.
Transport engines Postiz/n8n/browser/direct не являются production runtime.

Каждый provider изолирован по:

- module/capability;
- account;
- durable job queue;
- retry/backoff;
- circuit breaker;
- health/access state;
- reconciliation.

Падение одной платформы или одного аккаунта не останавливает остальные.
`ProviderSupervisor` фиксирует деградацию, сохраняет состояние и отправляет actionable alert.

Capability families:

| Capability | Примеры |
|---|---|
| `PublishingModule` | YouTube, Instagram, Facebook, Threads, TikTok, X, VK, LinkedIn |
| `MessagingModule` | WhatsApp, Viber, Telegram, LINE, Messenger, Slack, Discord |
| `IdentityModule` | OAuth/business/page/account discovery |
| `WebhookModule` | Meta, WhatsApp, TikTok, Viber, Telegram и др. |
| `MediaModule` | upload/resumable/chunked/media-container flows |

Полный provider inventory: `docs/PROVIDER-MATRIX.md` и `docs/FULL-SOCIAL-ORCHESTRATOR-ROADMAP-FINAL.md`.

Token broker (`token-broker.service`) — только опциональный credentials service; модульный runtime не зависит от Postiz.

## 7. Ручные загрузки (фича)

Сценарий: видео залито в соцсеть вручную → в панели «Ручные» → **Сканировать** → система
находит, сопоставляет с сущностями, **просит подтверждение**, проверяет клеймы, при
необходимости правит описание/ссылку и заносит в БД.

- Защита от «перекрёстного огня»: пост, созданный оркестратором, помечается `source`/`origin`: `module` | `remote` | `manual` | `platform` и исключается из кандидатов manual-scan.
- Сопоставление (`manual_uploads.match_score`): название (0.5), дата (0.3), длительность (0.2);
  вертикаль ищется среди вертикали.
- Всегда требуется подтверждение; по умолчанию `apply_edits=false`.
- Клеймы: Content ID через обычный Data API недоступен — ручная пометка + действие
  «Удалить/Оставить/Игнорировать».
- Расписание: `manual_uploads.schedule_scan: daily` (плюс кнопка).

API: `GET /webapp/api/manual/plan|uploads[?status&platform]|uploads/:id/candidates`,
`POST /webapp/api/manual/scan`, `.../uploads/:id/{confirm,reassign,reject,ignore,claim-action}`.

---

## 8. Веб-панель (WebApp)

- Публичный HTTPS (Cloudflare quick tunnel) → Menu Button бота.
- Разделы: **Статус, Папки, Ручные, Календарь, Очередь, Платформы, Хвост, Ошибки, Метрики,
  Действия, Справка**; язык **RU/EN** (переключатель, `localStorage`).
- Доступ: Telegram `initData` (whitelist) **или** ключ доступа (в пути `/webapp/k/<key>/`,
  в query `?key=` или заголовке `X-Webapp-Key`).
- Кэш: страница отдаётся «единым» HTML с инлайновыми JS/CSS; версия пути (`/webapp/b/NN/`)
  меняется при правках — обходит кэш Telegram-вью.
- Метрики: живые счётчики (очередь/опубликовано/ошибки) + рантайм (аптайм, циклы, sync).

---

## 9. MCP для ИИ

- **Оркестратор:** `scripts/mcp_server.py` — инструменты `orch_status/metrics/calendar/queue/
  platforms/failed/tail/roots/set_roots/browse/scan/pause/resume/resume_platform/series_end/
  distribute/force_link/manual_plan/manual_list/manual_scan/manual_confirm/manual_reject`.
Подключение opencode (`~/.config/opencode/opencode.jsonc`):

```jsonc
"mcp": {
  "orchestrator": { "type": "local",
    "command": ["python3", "/абсолютный/путь/scripts/mcp_server.py"],
    "environment": { "ORCH_URL": "http://<ORCH_HOST_IP>:8080", "ORCH_KEY": "<WEBAPP_ACCESS_KEY>" },
    "enabled": true }
}
```
Для Claude Desktop — тот же сервер через `mcpServers`.

> Historical MCP appendix — см. § Historical / deprecated в конце.

---

## 10. Telegram

- **Publisher-бот** используется для канала и панели (Menu Button).
- Команды бота: `/status /pause /resume /queue /failed /tail /platforms /distribute /calendar
  /app /reload_config …` (требуют `TELEGRAM_MODE=poll`).
- Whitelist: `telegram.allowed_chat_ids`.

---

## 11. Публичный доступ (HTTPS)

- `cloudflared-webapp.service` — quick tunnel на `http://127.0.0.1:8080`.
- `cloudflared-url-sync.timer` — раз в минуту обновляет
  Menu Button бота и `WEBAPP_PUBLIC_URL` при смене URL туннеля.
- Стабильный адрес (опц.): включить HTTPS в Tailscale (DNS → HTTPS Certificates) и
  перейти на `tailscale funnel 8080`, либо именованный Cloudflare-туннель.

---

## 12. База данных (SQLite `data/data.sqlite`, SCHEMA_VERSION=22)

`long_videos`, `shorts`, `entity_platform_status` (account-aware PK), `platform_accounts`,
`provider_access`, `provider_health`, `platform_queue_state`, `platform_safety_state`,
`publish_log`, `publish_attempts`, `outbox_events`, `durable_jobs`, `webhook_events`,
`distribution_targets`, `media_artifacts`, `consistency_runs`, `system_state`, **`platform_uploads`** (реестр
внешних/ручных загрузок; ключ `(engine, platform, platform_video_id)`; частичный UNIQUE 1:1
upload↔сущность). Миграции — в `db.py` (`SCHEMA_VERSION`).

---

## 13. Проверки и тесты

```bash
./scripts/check.sh      # ruff + compileall + node --check + pytest
./venv/bin/ruff check src scripts tests
PYTHONPATH=src ./venv/bin/python -m pytest tests/ -q
```
Хук: `.githooks/pre-commit` (включается `git config core.hooksPath .githooks`).
Текущее состояние: gate `scripts/gate_platform_zero.sh` + pytest (см. REPORT-HARD-CUT.txt).

---

## 14. Эксплуатация

| Действие | Команда |
|---|---|
| Статус | `systemctl status orchestrator.service` |
| Рестарт | `systemctl restart orchestrator.service` |
| Логи | `journalctl -u orchestrator.service -f` |
| Health | `curl http://127.0.0.1:8080/health` |
| Бэкап сейчас | `python -m orchestrator.main --backup` |
| Broker (VM) | `systemctl status token-broker.service` |
| Туннель | `systemctl status cloudflared-webapp.service` |

---

## 15. Диагностика (частые случаи)

- **Панель в Telegram показывает заглушку** — открой по свежей кнопке (меню обновляет
  `cloudflared-url-sync`); при смене сборки меняется путь `/webapp/b/NN/`.
- **`token broker: no token for youtube`** — на платформу не подключён YouTube-канал.
- **`HTTP Error 403` от брокера** — IP не в allowlist (`BROKER_ALLOW_IPS`).
- **TLS ошибки к platform API** — доверенный сертификат/CA; httpx `verify=True` по умолчанию (self-signed только локально через явный transport config).
- **Скан ручных:** `telegram: skipped` — у Telegram module нет list_remote (это нормально).

---

## 16. Ограничения и планы

- Нативные provider modules имеют честные состояния `IMPLEMENTED`, `SCAFFOLD`, `PARTNER`, `FEASIBILITY`; наличие каталога не означает live API access.
- Postiz/n8n/browser/direct legacy transports не являются частью production runtime.
- Content ID-клеймы не видны через Data API — ручная пометка.
- Плейсмент ручных загрузок не применяется (они уже опубликованы); планирование — задача
  `scheduler` (слоты/дни/время).

---

## 17. Документы

- `START.md` — быстрый старт (module path).
- `docs/PLATFORM_SETUP.md` — подключение площадок (YouTube/Telegram/Meta/TikTok).
- `deploy/README.md` — деплой и systemd (без Postiz VM).
- `docs/HANDOFF.md` — контекст между сессиями.
- `docs/FUNCTIONAL-REFERENCE-2026-10-01.md` — полный функциональный справочник текущего source tree: CLI, config/env, WebApp API, core API и все 42 provider-модуля.
- `docs/SESSION_LOG.md` — журнал работ.
- `REPORT-HARD-CUT.txt` — статус HARD_CUT / pytest / limitations.

### Historical / deprecated

Документы и env `POSTIZ_*`, Postiz VM/tunnel, `docs/POSTIZ_LIVE.md` — historical only (HARD_CUT). Не использовать как required onboarding.

Ранее: `scripts/postiz_mcp_server.py` с `POSTIZ_URL` / `POSTIZ_KEY` / `POSTIZ_VERIFY_TLS`, дефолт engine `postiz`, origin=`postiz`. Всё это снято с operational path; module path — единственный required runtime.

## Social Stack / Postiz-Free Expansion

The canonical architecture and provider coverage plan is documented in:
- `docs/ARCHITECTURE-MODULAR.md`
- `docs/PROVIDER-MATRIX.md`
- `docs/FULL-SOCIAL-ORCHESTRATOR-ROADMAP-FINAL.md`
- `REPORT-SOCIAL-ORCHESTRATOR-PREPARED.txt`

Provider modules are isolated by capability and account. A provider outage must
not stop unrelated providers; health/circuit state is exposed through the
orchestrator health surface. Provider entries marked `SCAFFOLD`, `PARTNER`, or
`FEASIBILITY` are not advertised as live Direct Publish integrations.


## API & launch playbook

Full cross-platform installation/one-click launch instructions and the per-provider API / Developer Access / App Review / Advanced Access runbook are in `API-AND-LAUNCH-GUIDE-2026-10-03.md` and `docs/API-AND-LAUNCH-GUIDE-2026-10-03.md`.
