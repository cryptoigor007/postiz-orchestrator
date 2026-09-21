# HANDOFF — передача в следующую сессию

> Прочитай этот файл первым. Он даёт полную картину: что за система, что сделано,
> что осталось, где что лежит и как это эксплуатировать.

Дата: 2026-09-21. Версия кода: `8.2.2`, UI-сборка **b816**, тестов: **305**.

---

## 0. Первые 5 минут (bootstrap новой сессии)

> Работать строго по протоколу `AGENTS.md` (репро → правка → check.sh → gui_check.sh → deploy → проверка).

```bash
cd /Users/dreamstore/Downloads/orchestrator
git pull && ./scripts/check.sh                      # 151 тест, линт
ssh root@100.95.225.71 'systemctl is-active orchestrator.service token-broker.service 2>/dev/null; echo ---; curl -s http://127.0.0.1:8080/health'
./scripts/runvm.sh 'systemctl is-active token-broker.service'   # хелпер к VM (см. §3)
```

Затем прочитать: `docs/HANDOFF.md` (этот файл) → `docs/SESSION_LOG.md` → `docs/VERIFICATION.md`.
И проверить актуальный URL панели: `ssh root@100.95.225.71 'cat /var/lib/cloudflared-webapp.url'`.

---

## 0.2 Оперативная сводка (2026-09-19, вечер)
- Сервер доступен по Wi-Fi **192.168.100.40** (USB-сетевой адаптер выдернут пользователем → у Postiz-VM нет
  интернета; **публикации не уйдут, пока адаптер не вернут**). Батарея ноутбука садится — нужна зарядка.
- SSD физически подключён к серверу, смонтирован ro в `/mnt/ssd_src` (utf8). Копирование на сервер
  приостановлено на 80 ГБ / ~292 ГБ: продолжение — `systemd-run --unit=ssd-backup bash /root/ssd_backup.sh`.
- В панели: обзор SSD (`WEBAPP_BROWSE_ROOT=/mnt/ssd_src,/mnt/video`), root может быть контейнером или серией.
- Watcher читает метаданные серий/шортсов (package_title, short_*_title.txt и т.д.) — посты с нормальными
  заголовками. Дальше: переформатировать SSD и вернуть данные (обсудить ФС).

---

## 1. TL;DR (состояние на сейчас)

- Система **работает и задеплоена**. Все сервисы active, тесты зелёные, GitHub синхронизирован.
- Оркестратор (публикации VideoMaker/ShortsMaker → Postiz → соцсети) + веб-панель + Telegram + MCP.
- **YouTube подключён** (канал `testPostiz`, тестовый). Telegram — канал `Postiz Test Channel`.
- Остались задачи, требующие пользователя: боевой YouTube, папки с видео (`/Volumes/SSD/untitled folder`), стабильный домен, ротация секретов.

---

## 2. Что это за система

```
VideoMaker/ShortsMaker ──► Orchestrator (Python, systemd, pve) ──► Postiz (VM 120) ──► соцсети
      (папки с видео)          watcher→scheduler→publisher→sync        docker
                                        │
             ┌──────────────────────────┼───────────────────────────┐
             ▼                          ▼                           ▼
      SQLite (data.sqlite)      Telegram-бот (уведомления)     WebApp (панель, Telegram Mini App)
                                        │
                                        └──── MCP ──► ИИ (opencode/Claude) ──► engines (postiz/direct/n8n/browser)
```

### Граф действий (ключевые потоки)

```mermaid
flowchart TD
  A[watch roots: сканирование папок] --> B[long_videos / shorts в SQLite]
  B --> C{платформы enabled?}
  C -->|да| D[scheduler: раскладка по слотам]
  D --> E[safety: лимиты/интервал/warmup]
  E --> F[ScheduleGuard: конфликты с Postiz/n8n]
  F -->|ок| G[publisher: upload + create post в Postiz]
  G --> H[entity_platform_status=scheduled]
  H --> I[status_sync: scheduled → published + release_url]
  I --> J[link_updater: ссылка в шортсы]
  I --> K[tail/backlog: остаток серии, хвост]
  L[manual uploads: скан соцсетей] --> M[сопоставление + подтверждение]
  M --> H
  N[webapp / MCP / Telegram] --> D
  N --> L
```

---

## 3. Инфраструктура и доступы

| Что | Значение |
|---|---|
| PVE-хост | `ssh root@100.95.225.71` (tailscale) / `192.168.100.50` (LAN/USB-NIC) / `192.168.100.40` (Wi-Fi), hostname `pve`. **Если на Mac Tailscale выключен** — работает LAN-адрес; `deploy.sh`/`runvm.sh` перебирают все три сами |
| VM Postiz | прямой `ssh postiz@192.168.100.60` с Mac (docker + passwordless sudo работают); хелпер `./scripts/runvm.sh '<cmd>'`; либо `qm guest exec 120 -- ...` с pve. Диск 234 ГБ, RAM 8 ГБ |
| Docker-стек | `postiz`, `postiz-nginx-https-1`, `postiz-db`, `postiz-redis`, `postiz-temporal`, `postiz-media` |
| Оркестратор | `/opt/orchestrator` на `pve`, пользователь `orchestrator` (systemd) |
| Compose Postiz | `/home/postiz/postiz/docker-compose.yml` (бэкапы `.bak.*`) |
| Postiz UI | https://192-168-100-60.sslip.io (nginx 443, самоподписанный) |
| Админ Postiz | `ko_geniy@mail.ru` / `00000000` |
| Webapp | cloudflared quick-tunnel, текущий URL в `/var/lib/cloudflared-webapp.url` |
| Репозиторий | `git@github.com:cryptoigor007/postiz-orchestrator.git` (private, ветка `master`) |
| Mac-путь | `/Users/dreamstore/Downloads/orchestrator` |

### Где лежат секреты (не в репозитории)
- `pve:/opt/orchestrator/.env` — `POSTIZ_API_TOKEN`, `WEBAPP_ACCESS_KEY`, `TELEGRAM_BOT_TOKEN`,
  `TOKEN_BROKER_SECRET`, `ORCH_BACKUP_MIRROR`, `TELEGRAM_MODE`.
- `VM:/etc/token-broker.env` — `BROKER_SECRET`, `BROKER_ALLOW_IPS`, `BROKER_PLATFORMS`.
- `VM:/home/postiz/postiz/docker-compose.yml` — пароли БД/Redis, `JWT_SECRET`,
  `YOUTUBE_CLIENT_ID/SECRET`.
- GitHub-доступ на Mac — в связке ключей (osxkeychain), remote HTTPS.

### MCP для ИИ (opencode)
- Конфиг: `~/.config/opencode/opencode.jsonc`, серверы **`orchestrator`** (`ORCH_URL`, `ORCH_KEY`)
  и **`postiz`** (`POSTIZ_URL`, `POSTIZ_KEY`, `POSTIZ_VERIFY_TLS`).
- Серверы: `scripts/mcp_server.py` (27 инструментов оркестратора), `scripts/postiz_mcp_server.py` (Postiz).
- После смены ключа в `/opt/orchestrator/.env` обновить и `ORCH_KEY` в конфиге MCP.

---

## 4. Что сделано (по сессиям, кратко)

### Исходная задача
Восстановить Postiz (self-hosted) и наладить панель/логику публикаций.

### Postiz
- Найден и исправлен **cookie domain** (`Domain=.sslip.io` → hostname без точки) и **nginx**:
  - `/api/` → backend со срезом префикса; `/auth/*` → фронтенд (страницы логина); `/public` → backend.
- Собран и задеплоен образ **`postiz-fixed:v1.47.2`** (фикс cookie, патчи; потоковая загрузка на диск, лимит 20 ГБ), compose переведён на него. Медиа: volume `postiz_uploads` → `/uploads`, env `UPLOAD_DIRECTORY=/uploads`, nginx `location /uploads/`.
- Подключён Telegram publisher-бот (`TELEGRAM_TOKEN`), канал `Postiz Test Channel`.
- Подключён YouTube (новый OAuth-клиент, канал `testPostiz`).

### Оркестратор (наш проект)
- Полный аудит и починка: `sync_updates`, календарь (слияние с Postiz), метрики, health.
- Веб-панель: разделы Статус/Папки/**Ручные**/Календарь/Очередь/Платформы/**Остаток**/Ошибки/Метрики/Действия/Справка,
  **RU/EN**, кэш-бастинг по путям сборки, полноэкранный режим, скрытая заглушка (CSS `[hidden]`).
- **Движки публикации** (`engines/`): `postiz`, `direct:youtube`, `n8n`, `browser (эксперим.)`;
  реестр возможностей и выбор движка в `config.engines`.
- **Ручные загрузки**: скан соцсетей → сопоставление (название/дата/длительность) →
  обязательное подтверждение → клеймы (ручная пометка + действия) → учёт в БД.
- **Остаток серии (backlog)**: вопрос за 60 мин до слота (15:00 для 16:00), кнопки
  «Распределить/Ждать/Не публиковать», напоминание за 15 мин, автодефолт к слоту;
  остаток **блокирует старт следующей серии**, пока не выложен.
- **Анти-коллизии расписаний**: `ScheduleGuard` сверяет слоты с Postiz (и n8n при `N8N_URL`),
  кэш 5 мин, окно настраивается (`safety.conflict_window_minutes`).
- **Платформенные папки**: `<серия>/youtube/final.mp4`, `<серия>/telegram/...`,
  `<серия>/shorts/short_01/youtube.mp4` (схема БД v10, поле `platform_paths`).
- **Токен-брокер** на VM: отдаёт OAuth-токен канала из Postiz, выбор канала по `id`,
  секрет + IP-allowlist (`192.168.100.50,127.0.0.1`).
- **Надёжность**: изоляция сбоев публикации, откат при неудачном пересоздании поста,
  авто-дефолт при пропущенном окне, ограниченный no-ack опрос Telegram (не крадёт `/connect`),
  джиттер не уводит в прошлое, зеркало бэкапов на другой диск.
- **Эксплуатация**: `scripts/check.sh` (ruff+compile+pytest), `scripts/deploy.sh` (безопасный
  rsync + chown + рестарт + синк кнопки), `infra-watchdog.timer` (панель/брокер/туннель → алерт),
  CI GitHub Actions (ruff+pytest).
- **MCP**: `scripts/mcp_server.py` (оркестратор, 27 инструментов), `scripts/postiz_mcp_server.py`
  (Postiz).

---

## 5. Команды (шпаргалка)

```bash
# локально (Mac)
cd /Users/dreamstore/Downloads/orchestrator
./scripts/check.sh                 # lint + compile + node + 151 тест
./scripts/deploy.sh                # безопасный деплой на pve + рестарт + синк кнопки

# на pve
ssh root@100.95.225.71
systemctl status orchestrator.service cloudflared-webapp.service cloudflared-url-sync.timer infra-watchdog.timer
journalctl -u orchestrator.service -f
curl -s http://127.0.0.1:8080/health
cat /var/lib/cloudflared-webapp.url

# на VM (с Mac, напрямую или через хелпер)
./scripts/runvm.sh 'systemctl status token-broker.service'
ssh postiz@192.168.100.60
systemctl status token-broker.service
docker ps
```

Проверка API панели (ключ — `WEBAPP_ACCESS_KEY` из `/opt/orchestrator/.env`):
```bash
curl -s "http://192.168.100.50:8080/webapp/api/status?key=<KEY>"
curl -s "http://192.168.100.50:8080/webapp/api/backlog?key=<KEY>"
```

---

## 6. Текущее состояние компонентов

- **Интеграции Postiz:** `telegram` → `Postiz Test Channel` (`cmu7g6kjq0001rw6wbwh46plb`),
  `youtube` → `testPostiz` (`cmu8el8yg0001nl7j89k74ht6`).
- **Конфиг** (`config.yaml`): `engines.youtube=direct`, `engines.telegram=postiz`;
  `platforms.youtube.integration_id=cmu8el8yg…`; `manual_uploads.schedule_scan=daily`;
  `tail.ask_minutes_before=60`, `default_action=distribute`; `safety.conflict_window_minutes=0`.
- **Watch roots:** сейчас одна папка (`/mnt/video/broll_downloads/Vertical/10_Precision_Cutting`).
- **Бэкапы:** `/opt/orchestrator/backups` + зеркало `/mnt/video/BACKUP_PVE/orchestrator`.
- **YouTube OAuth:** клиент `147375850159-mcarrb37r356s1aea6vlrf40bf83c7a2…`,
  consent в статусе Testing (аккаунт добавлен в Test users), redirect
  `https://192-168-100-60.sslip.io/integrations/social/youtube`.

---

## 6.5 Сеть сервера (схема после 2026-09-20)
- Интернет: **LAN (vmbr0, .50) — приоритет**, metric 100; **Wi-Fi (.40) — резерв**, metric 600.
  Переключение автоматическое (ядро по метрике), маршрут LAN добавляет/убирает ТОЛЬКО
  `/usr/local/sbin/lan-default.sh` (идемпотентно, владелец один; udev + раз в 60с из net-watchdog).
- Интернет для VM: `vm-nat.service` (`/usr/local/sbin/vm-nat.sh`) — MASQUERADE и FORWARD
  для vmbr0 И wlp2s0 (работает при любом аплинке).
- USB-LAN: udev `99-usb-r8152-restore.rules` -> `restore-usb-net.sh` + `lan-default.sh`.
- ЗАПРЕЩЕНО: любые скрипты с `nmcli disconnect/connect` в циклах и «война маршрутов»
  (см. docs/INCIDENT-2026-09-20-network.md). `infra-watchdog` алертит при их возврате.

## 7. Известные грабли и как чинить

| Симптом | Причина | Решение |
|---|---|---|
| `attempt to write a readonly database` | rsync от root сменил владельца | `chown -R orchestrator:orchestrator /opt/orchestrator`, деплой через `scripts/deploy.sh` |
| 502 на `/api/*` после пересоздания postiz | nginx держит старый IP контейнера | `docker restart postiz-nginx-https-1` (хелпер oauth уже делает сам) |
| Панель показывает заглушку | открыт старый/закэшированный URL | открыть свежую кнопку (build-путь меняется), меню обновляет `cloudflared-url-sync.timer` |
| `token broker: no token for ...` | канал не подключён в Postiz | подключить канал; при нескольких — указать `id` |
| `redirect_uri_mismatch` | URI не в OAuth-клиенте | добавить ровно `https://192-168-100-60.sslip.io/integrations/social/youtube` |
| `access_denied` (403) | аккаунт не в Test users | Google Auth Platform → Audience → Test users |
| `deleted_client` | OAuth-клиент удалён | создать новый и `bash /home/postiz/postiz/set_youtube_oauth.sh <id> <secret>` |
| Публикации нет, платформа «пауза» | случайная пауза из панели | раздел «Платформы» → «Возобновить» |
| Telegram не отвечает на команды | `TELEGRAM_MODE=off` | `TELEGRAM_MODE=poll` в `/opt/orchestrator/.env` + рестарт |

---

## 8. Что осталось (нужен пользователь)

1. **Боевой YouTube** — подключить реальный канал (аккаунт в Test users или Publish app);
   затем я переключу `integration_id` и проверю. Пользователь ведёт **один канал** «Наблюдения»
   (сейчас тестовый `testPostiz`), в перспективе — возможно несколько.
2. **Publish app (2 мин, за пользователем)** — Google Auth Platform → Audience → Publish app.
   Иначе refresh-токены живут 7 дней (каналы отваливаются еженедельно) и каждый аккаунт
   вручную вносится в Test users. После — добавление канала = 30 секунд в UI Postiz.
3. **Папки с видео** — `/Volumes/SSD/untitled folder` на Mac: расшарить (SMB) и смонтировать на
   pve, либо копировать/перенести SSD. Задать реальные watch roots.
4. **Стабильный домен** — Tailscale HTTPS (тумблер) → Funnel `pve.taile2eab6.ts.net`, или
   именованный Cloudflare-туннель (сейчас URL quick-tunnel меняется).
5. **Ротация секретов** — Postiz API key, webapp key, broker secret, GitHub-токен.
6. **n8n** — включится при `N8N_URL` (движок и анти-коллизии уже готовы).
7. **Экран выбора дня** для плейсмента — есть датапикер в «Остатке»; отдельный экран не делали.

### Планы пользователя (зафиксировано 2026-09-19, не делаем сейчас)
- **RuTube** — Postiz не поддерживает; план: n8n-воркфлоу (HTTP + OAuth2 к RuTube API),
  движок `n8n` уже готов. Нужны: n8n + токен RuTube API.
- **Фото/картинки** (сейчас только видео) — добавить watcher изображений (jpg/png) и
  публикацию картинок/каруселей через Postiz.
- **Склейка Shorts → длинное видео**: базово уже есть (`description_templates.thematic_short`,
  «▶ Полное видео: {link}»). Хочет усилить: закреплённый комментарий от имени канала,
  задержка 10–30 мин, шаблоны под платформы — против блокировок.
- **Мульти-канальность** (YouTube и др.) — на будущее: раскладка серия/проект → канал.
- Полный список доступных в Postiz провайдеров — см. `docs/SESSION_LOG.md` (сессия 2026-09-19).

---

## 9. Документы проекта

- `README.md` — обзор системы, конфиг, папки, эксплуатация.
- `docs/VERIFICATION.md` — чеклист проверки (от локальных тестов до live).
- `docs/SESSION_LOG.md` — журнал работ по датам и коммитам.
- `docs/superpowers/specs/2026-09-19-manual-upload-matching-design.md` — ТЗ ручных загрузок.
- `docs/superpowers/plans/2026-09-19-manual-uploads-engines-core.md` — план реализации.
- `docs/POSTIZ_LIVE.md`, `docs/ROLLBACK.md`, `docs/EMIL_SKILLS.md`.
- `deploy/README.md` — установка/обновление (безопасный rsync).
