# Текущие остатки и ops-задачи (единый список)

Обновлено: 2026-09-21 · версия **8.4.16 / b833** · тесты **364** · `./scripts/check.sh` PASS

Статусы: ✅ сделано в коде · 📝 задокументировано (осознанное решение) · 🧑 ops-задача владельца

## Закрыто по аудиту 2026-09-21

Полный отчёт с доказательствами: `docs/AUDIT-2026-09-21.md`.

| Пункт | Статус |
|---|---|
| **P0** path traversal в статике (`/webapp/b/<build>//etc/…` → `.env`/БД без ключа) | ✅ 8.4.5 |
| P1-1 дедлок `publishing` (safety-block/guard/read-only/hourly) | ✅ 8.4.6 |
| P1-2 флаг `--read-only` не работал | ✅ 8.4.6 |
| P1-4 `missing_in_postiz` не сбрасывался, `error` терминален | ✅ 8.4.6 |
| P1-7 слоты «в прошлом» при `start_date` | ✅ 8.4.6 |
| P1-8 пустой `POSTIZ_API_TOKEN` → тихий Mock | ✅ 8.4.6 |
| P1-10…P1-14 UI: вечный оверлей, «Остаток», «Ошибки»/«Справка», кнопка «Отменить», гонка `load()` | ✅ 8.4.7 |
| P2-1 обход rate-limit подделкой `X-Webapp-Key` | ✅ 8.4.8 |
| P2-2 IndexError календаря (пост без текста) | ✅ 8.4.8 |
| P2-3 ключ в логах legacy-пути `/webapp/k/<key>/` | ✅ 8.4.8 |
| P2-4 `queue/restore` fail-open при невалидном id | ✅ 8.4.8 |
| P2-5 `Content-Length: -1` (pre-auth hang) | ✅ 8.4.8 |
| P2-7 TLS verify OFF по умолчанию в Postiz MCP | ✅ 8.4.8 |
| P2-8 брокер: невалидный id → токен чужого канала | ✅ 8.4.8 (код; на VM не передеплоено) |
| P1-15 `deploy.sh` всегда «зелёный» | ✅ 8.4.8 |
| P1-3 бэклог-слоты из сырого конфига (override ломал раскладку) | ✅ 8.4.12 |
| P1-5 ответ «Ждать»/«Не публиковать» не сохранялся | ✅ 8.4.12 |
| P1-6 шторм загрузок при ошибке create | ✅ 8.4.13 |
| UI-аудит F1–F11 (блок `published`, `confirm` вне Telegram, каскадная метка, счётчики, i18n, плюрализация, дата, focus/Escape, favicon, SDK-guards) | ✅ 8.4.11 |
| N1–N3 (снятие с платформы, локализация ошибок, экран «Видео») | ✅ 8.4.14–8.4.15 |
| Trash `LIMIT 500` vs `all:true` | ✅ 8.4.12 |
| Корзина v2 (шапка/группы/пустое состояние/липкая панель) + видимая версия | ✅ 8.4.16 |

## Открыто

| # | Пункт | Статус |
|---|---|---|
| P1-9 | миграция v12→v13 путала soft-end и backlog | 🧑 прод уже на v14; решение: корректирующая миграция для других инсталляций или строка в доках |
| P1-16 | `yt_cleanup_test_videos.py` (refresh без `client_secret`) | 📝 ops-скрипт, демон не затронут |
| P2-батч | watcher `platform_paths`/junk-папки, WAL-бэкап перед миграцией, частичный `/reload_config`, 429 в Telegram | 📝 запланировано |
| N4 | 4xx в консоли браузера | 📝 путь `/browse` при пустых корнях убран (8.4.15); остальное — поведение браузера |
| C1 | реальный iPhone в Telegram | 🧑 один проход глазами (tabbar/шторка/корзина) |
| A7/E3 | ротация секретов | 🧑 чек-лист ниже |
| D4/D5 | Google OAuth → Publish app; именованный туннель | 🧑 |
| E2 | побайтовая сверка SSD | 🧑 нужен физически подключённый SSD к Mac |
| VM | `/opt/token_broker.py` не обновляется `deploy.sh` | 🧑 передеплой брокера на VM (фикс P2-8) |
| D1 | авто-удаление с платформ | 📝 есть «Снять с платформы» (8.4.14) для опубликованного; YouTube — через `direct` + токен-брокер |

## Безопасность / доступ

| # | Пункт | Статус |
|---|---|---|
| A1 | Учётка Postiz UI в git | ✅ пароль вычищен, **сменён**; новый — `VM:/home/postiz/postiz_admin_new_password.txt`, `pve:/root/postiz_admin_new_password.txt` (0600) |
| A2 | CSP `style-src 'unsafe-inline'` | ✅ инлайн-стилей нет; CSP строгий (script+style только `'self'` + per-request nonce) |
| A3 | Линтер «сырой innerHTML без esc()» | ✅ `scripts/check_xss.py` (в `check.sh` и CI) |
| A4 | `?key=` в URL и логах | ✅ ключ маскируется (`key=***` и `/webapp/k/***`), `Referrer-Policy: no-referrer` |
| A5 | `test_publish.enabled=true` | ✅ fail-closed по `test_integration_ids` + warning при пустом `prod_integration_ids` |
| A6 | `prod_integration_ids: []` | 📝 заполнить при переходе на боевые каналы |
| A7 | Секреты в истории git | 🧑 история не переписана (осознанно); пароль Postiz отозван, остальное — ротация |
| A8 | TLS к Postiz | ✅ verify включён через pinned CA `/etc/orchestrator/postiz-ca.pem` (+`PARTIAL_CHAIN`); сертификат до 2028-11-28 |
| A9 | Статика панели | ✅ 8.4.5: containment в `_file()` — произвольное чтение файлов закрыто (P0) |
| A10 | HTTP-вход | ✅ 8.4.8: `Content-Length` < 0 / нечисловой → 400; rate-limit не обходится подделкой заголовка |

**Ротация секретов (🧑 владельцу):** `POSTIZ_API_TOKEN`, `WEBAPP_ACCESS_KEY`, `TOKEN_BROKER_SECRET`,
`TELEGRAM_BOT_TOKEN`, GitHub PAT — заменить в `pve:/opt/orchestrator/.env`, `systemctl restart orchestrator`;
при смене webapp-ключа заново синхронизировать меню-кнопку (`/usr/local/bin/cloudflared_url_sync.sh`).

## Документация

| # | Пункт | Статус |
|---|---|---|
| B1 | Рассинхрон числа тестов | ✅ HANDOFF/README/AGENTS актуальны (364) |
| B2 | Устаревшая сводка §0.2 | ✅ обновлена |
| B3 | README «VACUUM INTO» | ✅ → `Connection.backup (sqlite_backup)` |
| B4 | AGENTS «200+ тестов» | ✅ → «≥322 + check.sh» |
| B5 | Единый residual | ✅ этот файл |
| B6 | FOUC EN→RU | ✅ подписи локализуются до показа `#app` |

## UI/UX

| # | Пункт | Статус |
|---|---|---|
| C1 | Нет smoke на реальном iPhone/Telegram | 🧑 открыть панель в Telegram на iPhone |
| C2 | 375px | ✅ измерено: 375×667 без переполнений |
| C3 | Degrade без fullscreen API | 📝 реализован (expand + 100% ширина/высота) |
| C4 | Много inline-стилей | ✅ = A2 |
| C5 | `esc` в опциях обложек | ✅ |
| C6 | Кэш `?v=` | ✅ синхронизирован со сборкой |
| C7 | Pixel-diff в CI | 📝 не делаем (нужен браузер в CI); есть jsdom-smoke + CDP-проверки |
| C8 | Иконки «Ещё» | ✅ свои SVG |
| C9 | Корзина: визуал | ✅ 8.4.16 (шапка/группы/пустое состояние/липкая панель) |
| C10 | Версия в приложении | ✅ 8.4.16 (шторка «Ещё» + «Справка»; сайдбар) |

## Логика / продукт

| # | Пункт | Статус |
|---|---|---|
| D1 | Postiz delete ≠ удаление с платформы | ✅ 8.4.14: «Снять с платформы» (Telegram=Postiz, YouTube=`direct`+broker) |
| D2 | TG media >50 МБ | ✅ предпроверка в publisher; боевой TG — link-only |
| D3 | `engines.youtube=direct` ≠ publish | 📝 `direct` — для manual-источников; публикация — Postiz HTTP |
| D4 | Google OAuth Testing (~7 дней) | 🧑 Publish app |
| D5 | Quick-tunnel URL плавает | 🧑 именованный tunnel/Funnel |
| D6 | SQLite один писатель | 📝 один сервис-писатель (systemd) |
| D7 | SMB/сетевые ФС | 📝 `file_stability_cycles` снижен |
| D8/D9 | `placement_default`, `audio_profile` | 📝 reserved (комментарии в `config.py`) |
| D10 | Instagram/TikTok/Facebook выключены | 📝 ожидаемо |
| D11 | Миграции только вперёд | ✅ авто-бэкап `backups/pre_migration_*.sqlite`; схема v14 |
| D12 | Молчаливые ошибки bulk | ✅ считаются и показываются в тосте |
| D13 | 429 Bot API живьём | 📝 юнит зелёный, живой 429 не форсировали |
| D14 | initData >24ч → 401 | ✅ тост «Сессия устарела — открой панель заново» |

## Инфра

| # | Пункт | Статус |
|---|---|---|
| E1 | Боевые каналы | 🧑 переключить YouTube/канал, когда владелец решит |
| E2 | Watch roots / SSD | 📝 `/mnt/video` + `/mnt/ssd_src`; побайтовая сверка SSD на паузе |
| E3 | Ротация секретов | 🧑 чек-лист выше |
| E4 | CI | ✅ xss/csp linter + pytest + jsdom GUI-smoke |
| E5/E6 | Тест-ids и chat_ids в config | 📝 приватный репозиторий; при публикации — `config.local.yaml` |

## Качество кода

| # | Пункт | Статус |
|---|---|---|
| F1 | `except Exception: pass` без лога | ✅ логируется |
| F2 | README backup | ✅ = B3 |
| F3 | Счётчик тестов | ✅ = B1 |
| F4 | `manual_uploads.platforms: []` | 📝 комментарий в `config.py` |
| F5 | Thumb URL с ключом | ✅ = A4 |
