# Orchestrator

Пайплайн публикаций: **VideoMaker + ShortsMaker → Postiz → соцсети**, с веб-панелью (Telegram
WebApp), Telegram-ботом, MCP-интеграцией для ИИ и модулем распознавания ручных загрузок.

Версия: `8.4.16` (b833).

> Передача контекста между сессиями — `docs/HANDOFF.md` (читать первым).

---

## 1. Что есть в системе (общая картина)

```
VideoMaker/ShortsMaker  ──►  Orchestrator (Python, systemd)  ──►  Postiz  ──►  соцсети
   (папки с видео)             watcher→scheduler→publisher        (VM 120)     (Telegram, YouTube, …)
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
| **Orchestrator** | PVE-хост `pve`, systemd | сканирует папки, планирует, публикует через Postiz, синхронизирует статусы |
| **WebApp** | HTTP `:8080` на `pve` | панель управления (10 разделов), доступ через Telegram Menu Button |
| **Telegram-бот** | publisher-бот Postiz | команды управления + приём отчётов |
| **Postiz** | VM 120 (docker) | хранилище каналов/OAuth, публикация в соцсети |
| **Token broker** | VM 120 (`token-broker.service`) | отдаёт оркестратору OAuth-токен канала из БД Postiz |
| **Cloudflare tunnel** | `pve` | публичный HTTPS на webapp (временный URL) |
| **MCP-серверы** | на машине ИИ-клиента | инструменты оркестратора и Postiz для ИИ |

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
  postiz_http.py     HTTP-клиент публичного API Postiz
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
  engines/           движки публикации (см. §6)
scripts/
  check.sh               ruff + compileall + node --check + pytest
  mcp_server.py          MCP-сервер оркестратора (stdio)
  postiz_mcp_server.py   MCP-сервер Postiz (stdio)
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
2. **sync** (`status_sync_interval_sec`, 180с): подтягивает статусы постов из Postiz
   (`scheduled → published`), обновляет `release_url`, подставляет ссылку в шортсы
   (`link_updater`), работает «хвост» (`tail`).
3. **recon** (раз в `reconciliation_interval_hours`, 24ч): сверка «наши ↔ Postiz»
   (пропавшие/сироты).
4. **backup** (`interval_hours`, 6ч): `sqlite3 Connection.backup` в `backups/`, хранение `keep_days`; перед миграциями схемы — автобэкап `pre_migration_*.sqlite` (D11).
5. **manual scan** (`schedule_scan: daily`): поиск ручных загрузок в соцсетях (§7).

Публикация (`publisher.py`): идемпотентно (ключ `entity_type:entity_id:platform:время`),
upload медиа → create post в Postiz, запись статуса, jitter и лимиты.

Сущности БД: `long_videos`, `shorts`; статусы на платформу — `entity_platform_status`
(`status`, `postiz_post_id`, `postiz_scheduled_for`, `release_url`, …).

---

## 4. Конфигурация

### 4.1 `config.yaml` (поведение)

- `schedules` — расписание: `long_video` (вт/пт 16:00), `shorts_standalone`
  (пн/ср/чт/сб/вс в 12:00 и 18:00), `shorts_thematic` (default 20:30).
- `platforms` — каналы: `enabled`, `video_variant` (wide/vertical), `daily_limit`,
  `integration_id` (ID канала из Postiz).
- `engines` — движки для **manual_uploads** (скан/list/claims), не маршрут основного `Publisher` (см. §6); дефолт `postiz`.
- `manual_uploads` — параметры распознавания ручных загрузок (§7).
- `tail`, `limits`, `link_update`, `description_templates`, `safety`, `telegram`,
  `backup`, `timezone`, интервалы.

### 4.2 `.env` (секреты/адреса; git-ignored)

| Ключ | Назначение |
|---|---|
| `POSTIZ_BASE_URL` | вход Postiz (nginx/slip) |
| `POSTIZ_API_TOKEN` | API-ключ организации (raw `Authorization`) |
| `POSTIZ_AUTH_STYLE=raw` | без Bearer |
| `POSTIZ_PATH_UPLOAD`, `POSTIZ_PATH_POSTS` | пути публичного API |
| `POSTIZ_VERIFY_TLS` | **по умолчанию проверка ВКЛ**; `=0` — только для локальной отладки (self-signed), в бою не использовать |
| `TELEGRAM_BOT_TOKEN` | publisher-бот |
| `TELEGRAM_MODE=poll\|off` | long-poll команд (off мешает конфликтам getUpdates) |
| `WEBAPP_PUBLIC_URL` | публичный URL панели |
| `WEBAPP_ACCESS_KEY` | ключ доступа к панели |
| `WEBAPP_BROWSE_ROOT` | разрешённые корни обзора папок (через запятую) |
| `TOKEN_BROKER_URL`, `TOKEN_BROKER_SECRET` | доступ к брокеру токенов |
| `N8N_URL`, `N8N_TOKEN` | активация n8n-движка (опц.) |

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
- Direct YouTube transport: TLS verify **on** by default (`DirectHttpTransport(verify=True)`).
- Health HTTP bind: `ORCH_HTTP_BIND` (default `127.0.0.1`); metrics may require `ORCH_HEALTH_TOKEN`.
- `ORCH_READ_ONLY=1` blocks publish creates.

## 6. Движки (`engines/`) — честно о scope

**Важно (v7):** основной publish-path (`Publisher`) ходит **только в Postiz HTTP-клиент**.
`config.engines.<platform>` используется для **manual_uploads** (скан/list/claims ручных
загрузок), а **не** как маршрут обычной публикации long/thematic/standalone.

| Движок | Умеет | Где реально используется |
|---|---|---|
| `postiz` | publish, delete | основной `Publisher` + manual |
| `direct` | list, update, claims (YouTube) | **только** manual_uploads / claims |
| `n8n` | publish, list | manual / экспериментально (`N8N_URL`) |
| `browser` | экспериментальный | не в основном publish-path |

Полный publish-through-engine — отдельное решение (не текущий runtime).

**Token broker** (`token-broker.service` на VM 120) отдаёт OAuth-токен канала из Postiz
(таблица `Integration`) оркестратору, недоступному к docker-сети. Ограничен секретом
(`X-Broker-Secret`) и IP-allowlist. Эндпоинты: `/health`, `/token?platform=`.

---

## 7. Ручные загрузки (фича)

Сценарий: видео залито в соцсеть вручную → в панели «Ручные» → **Сканировать** → система
находит, сопоставляет с сущностями, **просит подтверждение**, проверяет клеймы, при
необходимости правит описание/ссылку и заносит в БД.

- Защита от «перекрёстного огня»: пост, созданный любым движком, помечается `origin=postiz`
  и исключается из кандидатов (по известным id и `creationMethod`).
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
- **Postiz:** `scripts/postiz_mcp_server.py` — `postiz_integrations/posts/upload_from_url/
  create/delete/set_status`.

Подключение opencode (`~/.config/opencode/opencode.jsonc`):

```jsonc
"mcp": {
  "orchestrator": { "type": "local",
    "command": ["python3", "/абсолютный/путь/scripts/mcp_server.py"],
    "environment": { "ORCH_URL": "http://192.168.100.50:8080", "ORCH_KEY": "<WEBAPP_ACCESS_KEY>" },
    "enabled": true },
  "postiz": { "type": "local",
    "command": ["python3", "/абсолютный/путь/scripts/postiz_mcp_server.py"],
    "environment": { "POSTIZ_URL": "https://192-168-100-60.sslip.io",
                     "POSTIZ_KEY": "<API key>", "POSTIZ_VERIFY_TLS": "0" },
    "enabled": true }
}
```
Для Claude Desktop — тот же сервер через `mcpServers` (см. §«MCP» в docs).

---

## 10. Telegram

- **Publisher-бот** используется для канала и панели (Menu Button).
- Команды бота: `/status /pause /resume /queue /failed /tail /platforms /distribute /calendar
  /app /reload_config …` (требуют `TELEGRAM_MODE=poll`; не включать, пока Postiz подключает
  каналы, чтобы не «съедать» `/connect`).
- Whitelist: `telegram.allowed_chat_ids`.

---

## 11. Публичный доступ (HTTPS)

- `cloudflared-webapp.service` — quick tunnel на `http://127.0.0.1:8080`.
- `cloudflared-url-sync.timer` — раз в минуту обновляет
  Menu Button бота и `WEBAPP_PUBLIC_URL` при смене URL туннеля.
- Стабильный адрес (опц.): включить HTTPS в Tailscale (DNS → HTTPS Certificates) и
  перейти на `tailscale funnel 8080`, либо именованный Cloudflare-туннель.

---

## 12. База данных (SQLite `data/data.sqlite`, схема v9)

`long_videos`, `shorts`, `entity_platform_status`, `platform_queue_state`,
`platform_safety_state`, `publish_log`, `system_state`, **`platform_uploads`** (реестр
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
Текущее состояние: **110 тестов passed**, линт чист.

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
- **`token broker: no token for youtube`** — в Postiz не подключён YouTube-канал.
- **`HTTP Error 403` от брокера** — IP не в allowlist (`BROKER_ALLOW_IPS`).
- **TLS ошибки к Postiz** — правильный путь: доверенный сертификат/CA; `POSTIZ_VERIFY_TLS=0` — только временно и локально (A8).
- **Скан ручных:** `telegram: skipped` — у Postiz-движка нет листинга (это нормально).

---

## 16. Ограничения и планы

- `direct` реализован для YouTube; остальные платформы — по мере добавления адаптеров.
- `browser`-движок — экспериментальный (по решению подключается последним).
- Content ID-клеймы не видны через Data API — ручная пометка.
- Плейсмент ручных загрузок не применяется (они уже опубликованы); планирование — задача
  `scheduler` (слоты/дни/время).

---

## 17. Документы

- `docs/superpowers/specs/2026-09-19-manual-upload-matching-design.md` — ТЗ фичи ручных загрузок.
- `docs/superpowers/plans/2026-09-19-manual-uploads-engines-core.md` — план реализации.
- `docs/SESSION_LOG.md` — журнал работ и коммитов.
- `docs/POSTIZ_LIVE.md`, `docs/ROLLBACK.md`, `docs/EMIL_SKILLS.md` — дополнительно.
- `deploy/README.md` — деплой и установка.
