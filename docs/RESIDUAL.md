# Текущие остатки и ops-задачи (единый список)

Обновлено: 2026-09-21 · версия **8.3.2 / b820** · тесты 323 · `./scripts/check.sh` PASS

Статусы: ✅ сделано в коде · 📝 задокументировано (осознанное решение) · 🧑 ops-задача владельца

## Безопасность / доступ

| # | Пункт | Статус |
|---|-------|--------|
| A1 | Учётка Postiz UI в git | ✅ пароль вычищен из `docs/HANDOFF.md`; **пароль сменён** (bcrypt), старый отвергается, новый — в `VM:/home/postiz/postiz_admin_new_password.txt` и `pve:/root/postiz_admin_new_password.txt` (0600) |
| A2 | CSP `style-src 'unsafe-inline'` | ✅ инлайн-стилей больше нет (0 в `app.js`/`index.html`); CSP строгий: script+style только `'self'` + per-request nonce |
| A3 | Нет линтера «сырой innerHTML без esc()» | ✅ `scripts/check_xss.py` (+ в `check.sh` и CI) |
| A4 | `?key=` в URL и логах | ✅ ключ маскируется в логах (`key=***`), `Referrer-Policy: no-referrer`; 📝 сам `?key=` нужен для меню Telegram WebApp (авторизация в панели) |
| A5 | `test_publish.enabled=true` в config | ✅ fail-closed по `test_integration_ids` + предупреждение при пустом `prod_integration_ids`; 📝 контур включён только для тест-каналов |
| A6 | `prod_integration_ids: []` | 📝 заполнить при переходе на боевые каналы (иначе тест запрещён — это безопасно) |
| A7 | Секреты в истории git | 🧑 история не переписана (осознанно); пароль Postiz уже отозван; остальное — ротация по списку ниже |
| A8 | TLS к Postiz | ✅ **verify включён**: pinned CA `/etc/orchestrator/postiz-ca.pem` (+`VERIFY_X509_PARTIAL_CHAIN`); `POSTIZ_VERIFY_TLS=0` больше не используется. Сертификат действителен до 2028-11-28 — при перевыпуске обновить файл и рестартовать |

**Ротация секретов (🧑 владельцу):** `POSTIZ_API_TOKEN`, `WEBAPP_ACCESS_KEY`, `TOKEN_BROKER_SECRET`, `TELEGRAM_BOT_TOKEN`, GitHub PAT — команды: заменить в `pve:/opt/orchestrator/.env`, `systemctl restart orchestrator`, при смене webapp-ключа — заново синхронизировать меню-кнопку (`/usr/local/bin/cloudflared_url_sync.sh`).

## Документация

| # | Пункт | Статус |
|---|-------|--------|
| B1 | Рассинхрон числа тестов | ✅ HANDOFF/README/AGENTS → 322 / b820 |
| B2 | Устаревшая сводка §0.2 | ✅ обновлена (LAN-primary, SSD на паузе, версия) |
| B3 | README «VACUUM INTO» | ✅ → `Connection.backup (sqlite_backup)` |
| B4 | AGENTS «200+ тестов» | ✅ → «≥322 + check.sh» |
| B5 | Нет единого residual | ✅ этот файл (`docs/RESIDUAL.md`) |
| B6 | FOUC EN→RU | ✅ подписи локализуются до показа `#app`; в HTML — RU-дефолты |

## UI/UX

| # | Пункт | Статус |
|---|-------|--------|
| C1 | Нет smoke на реальном iPhone/Telegram | 🧑 один раз открыть панель в Telegram на iPhone (проверить tabbar/шторку/cover-лист) |
| C2 | 375px | ✅ измерено: 375×667 — `docScrollW=375`, 5 табов, карточки 2×167.5, переполнений нет |
| C3 | Degrade без fullscreen API | 📝 реализован (expand + 100% ширина/высота), на старом клиенте визуально не проверялся |
| C4 | Много inline-стилей | ✅ = A2 |
| C5 | `esc` в опциях обложек | ✅ добавлен |
| C6 | Кэш `?v=` | ✅ синхронизирован с build (820); страница и так инлайнит CSS/JS + no-store |
| C7 | Pixel-diff в CI | 📝 не делаем: нужен браузер в CI; есть jsdom-smoke (`scripts/ci_gui_smoke.sh`) + CDP-проверки вручную |
| C8 | Иконки «Ещё» | 📝 свои SVG (gear/chart/help и т.д.) — косметика |

## Логика / продукт

| # | Пункт | Статус |
|---|-------|--------|
| D1 | Postiz delete ≠ удаление с платформы | 📝 метод: `scripts/yt_cleanup_test_videos.py` (YouTube через broker+engine), Telegram-сообщение — админ-ботом (`deleteMessage`); авто-удаление с платформ не делаем осознанно |
| D2 | TG media >50 МБ | ✅ предпроверка в publisher (понятная ошибка до создания поста); 📝 боевой TG — link-only |
| D3 | `engines.youtube=direct` ≠ publish | 📝 `direct` используется для manual-источников; публикация — Postiz HTTP |
| D4 | Google OAuth Testing (~7 дней) | 🧑 опубликовать OAuth-приложение (Publish app) |
| D5 | Quick-tunnel URL плавает | 🧑 именованный tunnel/Funnel (нужен домен Cloudflare) |
| D6 | SQLite один писатель | 📝 один сервис-писатель (systemd), так и задумано |
| D7 | SMB/сетевые ФС | 📝 снижено `file_stability_cycles` (размер стабилен 2 цикла) |
| D8 | `placement_default` | 📝 reserved (комментарий в config.py) |
| D9 | `audio_profile` | 📝 reserved (комментарий) |
| D10 | Instagram/TikTok/Facebook выключены | 📝 ожидаемо |
| D11 | Миграции только вперёд | ✅ авто-бэкап `backups/pre_migration_*.sqlite` перед миграцией |
| D12 | Молчаливые ошибки bulk | ✅ ошибки считаются и показываются в тосте + `console.warn` |
| D13 | 429 Bot API живьём | 📝 юнит-тест зелёный, живой 429 не форсировали |
| D14 | initData >24ч → 401 | ✅ понятный тост «Сессия устарела — открой панель заново из бота» |

## Инфра

| # | Пункт | Статус |
|---|-------|--------|
| E1 | Боевые каналы | 🧑 переключить YouTube/канал, когда владелец решит |
| E2 | Watch roots / SSD | 📝 `/mnt/video` + `/mnt/ssd_src` в browse; побайтовая сверка SSD на паузе |
| E3 | Ротация секретов | 🧑 чек-лист выше (A7/A8) |
| E4 | CI без GUI | ✅ `xss/csp linter` + `GUI smoke (jsdom)` шаги |
| E5/E6 | Тест-ids и chat_ids в config | 📝 приватный репозиторий; при публикации — вынести в `config.local.yaml` |

## Качество кода

| # | Пункт | Статус |
|---|-------|--------|
| F1 | `except Exception: pass` без лога | ✅ заменено на `logger.debug(..., exc_info=True)` в затронутых местах |
| F2 | README backup | ✅ = B3 |
| F3 | Счётчик тестов | ✅ = B1 |
| F4 | `manual_uploads.platforms: []` | 📝 комментарий в config.py: пусто = все источники |
| F5 | Thumb URL с ключом | ✅ = A4 |
