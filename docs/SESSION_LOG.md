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

## 2026-09-19 — Ручные загрузки (ТЗ + реализация)
- Написано ТЗ: `docs/superpowers/specs/2026-09-19-manual-upload-matching-design.md`.
- Скан соцсетей (Postiz-интеграции + direct), сопоставление с сущностями БД
  (нормализация имён, дата ±окно, длительность), обязательное подтверждение пользователем.
- Схема БД v10: таблица `platform_uploads`, поле `platform_paths` (per-platform файлы).
- UI: раздел «Ручные» (найти/подтвердить/переназначить), ручная пометка клейма.
- Поддержка схем папок: `<series>/<platform>/final.mp4`, `<series>/shorts/short_XX/<platform>.mp4`.

## 2026-09-19 — Движки публикации
- `engines/`: базовый интерфейс, реестр, `postiz_engine`, `direct_youtube`, `n8n_engine`, `browser_engine` (эксперим.).
- Токен-брокер на VM (`token-broker.service`): выдаёт OAuth-токены каналов из Postiz по платформе,
  секрет + IP-allowlist; клиент брокера в оркестраторе.
- MCP: расширенный набор инструментов оркестратора и Postiz.

## 2026-09-19 — Веб-панель: полировка
- Полный RU/EN, переименования (Хвост→«Остаток», «Сверка с Postiz»), локализованные статусы,
  кэш-бастинг сборок (`/k/<key>/b/<build>/`), скрытая заглушка `[hidden]`.

## 2026-09-19 — GitHub + CI
- Репозиторий `cryptoigor007/postiz-orchestrator` (private). Ветка `master`.
- `.github/workflows/ci.yml`: ruff + pytest (зелёный).
- Деплой: `scripts/deploy.sh` (rsync без root-владельца, серверный chown, рестарт, синк кнопки).

## 2026-09-19 — Backlog («Остаток серии»)
- Вопрос за 60 мин до слота, кнопки «Распределить остаток / Ждать ещё / Не публиковать»,
  напоминание за 15 мин, автодефолт к слоту, блокировка следующей серии до выкладки остатка,
  датапикер для плейсмента.

## 2026-09-19 — Hardening логики
- Изоляция сбоев публикации (одна платформа ≠ весь цикл), откат при неудачном пересоздании поста,
  авто-дефолт при пропущенном окне, ограниченный no-ack опрос (не крадёт Telegram `/connect`),
  джиттер не в прошлое, чистка зеркала бэкапов.

## 2026-09-19 — Анти-коллизии расписаний
- `ScheduleGuard`: сверка слотов с Postiz (кэш 5 мин) и n8n (при `N8N_URL`), окно конфликтов
  настраивается (`safety.conflict_window_minutes`).

## 2026-09-19 — YouTube OAuth: подключение
- Починены cookie Postiz (образ `postiz-fixed:v1.47.0`) и nginx (`/api/` → backend со срезом
  префикса; `/auth/*` → фронтенд).
- OAuth: `redirect_uri_mismatch` и `deleted_client` устранены сменой клиента; хелпер
  `deploy/set_youtube_oauth.sh` (в compose + ожидание backend перед restart nginx).
- `access_denied`: аккаунт добавлен в Test users; затем выяснилось — у аккаунта нет канала.
- Пользователь создал канал **testPostiz**; интеграция подключена
  (`cmu8el8yg0001nl7j89k74ht6`), `channels.list` возвращает канал, живой скан YouTube — ok.

## 2026-09-19 — Переключение каналов YouTube
- Токен-брокер: выбор канала по `id` (`/token?platform=youtube&id=…`), SQL-фильтр + валидация id.
- Оркестратор: `manual_sources` передаёт `platforms.<p>.integration_id` в брокер.
- Привязка канала в `config.yaml → platforms.youtube.integration_id`.

## 2026-09-19 — Handoff
- Создан `docs/HANDOFF.md`: полная карта системы, граф действий, доступы, состояние,
  грабли и лечение, что осталось, шпаргалка команд.

## 2026-09-19 — Переключение на пробный постинг
- Копирование SSD поставлено на паузу на 80 041 МБ / ~292 000 (состояние: `/root/ssd_backup_state.txt`
  на сервере; продолжение: `systemd-run --unit=ssd-backup bash /root/ssd_backup.sh` — rsync докачает).
- SSD подключён к серверу и смонтирован **ro с iocharset=utf8** в `/mnt/ssd_src` (у оркестратора доступ на чтение;
  МАСШТАБ: монтаж ручной — переживёт до перезагрузки/отключения диска).
- Сервер вернулся в сеть **по Wi-Fi `192.168.100.40`** (tailscale снова up). USB-сетевой адаптер выдернут →
  у Postiz-VM нет интернета: публикации в соцсети не уйдут, пока адаптер не вернут. Батарея разряжается (нужна зарядка).
- Панель: `WEBAPP_BROWSE_ROOT=/mnt/ssd_src,/mnt/video` — SSD виден в браузере папок Mini App.
- Watcher: парсит `info_metadata.txt` (`package_title`/`package_hook`/`package_hashtags`) и мета-файлы
  шортсов (`*_title/_description/_hashtags/_hook/_upload.txt`, `*_cover.*`); root может быть как контейнером
  серий, так и самой серией. Тесты 153.
- `deploy.sh`/`runvm.sh`: добавлен кандидат `root@192.168.100.40`.

## 2026-09-19 — Умное сканирование (рекрусивные детекторы)
- Новый watcher: рекурсивный обход (глубина `watch_max_depth=5`), строгие детекторы «маркер+видео»:
  эпизод VideoMaker, шортс Shorts Maker (`*_final.mp4` + мета), россыпь mp4 с мета.
- Мусор отсекается по именам (`_*`, `._*`, `.Spotlight`, `$RECYCLE.BIN`, `*.app`, `*overflow*`).
- Парсинг меты Shorts Maker: «Заголовок:/Описание:» из `*_titles.txt`, хук, хэштеги, обложка.
- Платформенные папки внутри эпизода → `platform_paths` (разные аудио для соцсетей).
- UI: «+ Добавить эту папку», корни обзора реальными путями (b29).
- Спека: `docs/superpowers/specs/2026-09-19-smart-scan-design.md`. Тесты 156.

## 2026-09-19 — Пробный запуск публикаций (вечер)
- VM после смены сети потеряла IP (DHCP недоступен без USB-NIC) → выдан статический 192.168.100.60,
  шлюз через хост (192.168.100.50), DNS 1.1.1.1/8.8.8.8 (`/etc/netplan/50-cloud-init.yaml`).
- Интернет для Postiz-VM поднят через Wi-Fi хоста: NAT (`vm-nat-wifi.service` + sysctl) — USB-сетевой
  адаптер больше не обязателен (у пользователя конфликт портов: зарядка/SSD/адаптер).
- Найдены и исправлены баги публикации:
  1) ScheduleGuard видел посты всех платформ → самоблокировка YouTube; теперь фильтр по платформе;
  2) `get_post` считал пост отсутствующим при 404 от single-get (в этой версии Postiz его нет) →
     ложный `missing_in_postiz`; теперь fallback на список, ошибки не глотаются;
  3) Postiz для YouTube требует `settings` (title 2..100, type public/private/unlisted,
     selfDeclaredMadeForKids, tags ≤500 симв.) — добавлен `_platform_settings`.
- Результат: пробный фильм «проба_40сек» запланирован в **Telegram и YouTube** на вт 16:00 MSK
  (postiz id cmu8ov6n8… / cmu8pa726…); лишние дубли переведены в DRAFT; reconcile: missing=0.
- Сканер: проба = 1 фильм + 4 шортса с настоящими заголовками; режим «маркер+видео» работает.
- Тесты 157. Постинг уйдёт по расписанию (вт 16:00; шортсы серии — 20:30).

## 2026-09-19 — Папки с типами, расписания по соцсетям, группы (b30)
- Раздел «Папки»: тип корня (Авто/Серии/Shorts), кнопки «+ Сериалы/+ Shorts/+ Авто», переключение типа (⇄).
  Watcher: `series` — только серии, `shorts` — только шортсы (без фильмов), `auto` — как раньше; legacy-строки → auto.
- Раздел «Расписание»: настройки по каждой соцсети отдельно — серии (дни+время), тематические шортсы (время),
  обычные шортсы (дни+времена), лимит в день; кнопки Сохранить/Сбросить. Хранение в БД (`schedule_settings`).
- Группы соцсетей (`network_groups`): общий таймер — сети из группы публикуются одновременно
  (настройки группы приоритетнее настроек платформы).
- API: `GET/POST /roots` (items с kind), `GET/POST /schedule_settings`, `POST /groups` + валидация; тесты 164.
- Live-проверка: group override (17:00) применился и сброшен; очередь вт 16:00 (TG+YT) не тронута; scan идемпотентен.
