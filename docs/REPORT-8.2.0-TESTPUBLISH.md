# Отчёт 8.2.0 — тестовый контур публикации (`test_publish`) + закрепление H1–H3

**Дата:** 2026-09-21 · **Версия:** 8.2.0 · **Сборка панели:** b814 · **Коммит:** `133286d` (запушен в GitHub master)
**Тесты:** 255 (было 239, +16) · **ruff:** 0 замечаний · `check.sh` и `gui_check.sh` — зелёные
**Откат:** `/root/orchestrator_rollback_20260921_133459.tar.gz` (16 МБ, снят перед деплоем)

## A. Тестовый контур публикации (test_publish)

**Замысел:** проверить боевой путь публикации (Postiz → канал) на тестовом канале, **не задевая боевую сетку**.

**Ключевое свойство (главное отличие от «поставить тест в очередь»):** пробный пост создаётся тем же клиентом
и тем же медиа-путём (symlink-broker), но **напрямую в Postiz**, без записи в `entity_platform_status` —
боевые строки расписания не подменяются и не удаляются. Факт фиксируется только в журнале `publish_log`
(`test_scheduled` / `test_dry_run` / `test_cancelled`).

**Конфиг** (`config.yaml`, по умолчанию выключено):
```yaml
test_publish:
  enabled: true                 # контур доступен (включён для тестовых каналов)
  default_delay_minutes: 1      # +1 мин по умолчанию
  min_delay_minutes: 1
  max_delay_minutes: 120
  title_prefix: "[orch-test] "  # префикс заголовка И тела сообщения
  platforms: ["youtube", "telegram"]   # allowlist
  require_explicit_platforms: true
  allow_prod_channel: false
  prod_integration_ids: []      # при переходе на боевые каналы — вписать их id
  skip_tail_side_effects: true  # хвост/тематические каскады НЕ запускаются
  skip_thematic_cascade: true
  zero_jitter: true             # без джиттера (точное время проверки)
```

**API** (панель, ключ как обычно; read-only → 403 для всех POST, включая новые):
- `POST /webapp/api/test/schedule` → `{platforms:[...], delay_minutes?, scheduled_for?, entity_type, entity_id, dry_run?}`
- `GET /webapp/api/test/status` → состояние контура + последние тесты
- `POST /webapp/api/test/cancel` → удаление **только** помеченных `test_scheduled` (иначе 404)

**UI:** Actions → панель «Проверка (тестовый пост)»: платформа из allowlist, задержка (мин), сущность из очереди,
кнопки **Тест-пост** / **Dry-run**, список последних тестов с кнопкой «Отменить» (i18n ru/en).
**CLI:** `--test-schedule --test-platform youtube --test-entity short:270 [--test-delay N] [--test-dry-run]`.

**Безопасность:**
- allowlist платформ (платформа вне списка → 403), `require_explicit_platforms`;
- prod-guard: `integration_id` из `prod_integration_ids` при `allow_prod_channel:false` → 403;
- границы задержки 1–120 мин; `scheduled_for` только в будущем;
- никаких вызовов раскладки/хвоста/тематического каскада — только создание поста;
- link-режим Telegram: тест = **ссылка** на YouTube из `release_url` (как боевой формат канала), медиа не грузится;
- media-режим: предохранитель Bot API Telegram — файл >45 МБ → 400 с понятным текстом.

## B. Закрепление H1–H3 жёсткого прогона (+ новые тесты)

| Кейс | Тест | Статус |
|---|---|---|
| H1 SSRF (cover/fetch: private/loopback/link-local, redirect ≤3, только image) | `test_residual_closure.py::test_host_is_public_blocks_private` | ✓ |
| H2 429 ретраится | `test_postiz_http.py::test_post_429_is_retried` | ✓ |
| H2-антидубль: POST 5xx/timeout НЕ ретраится | `test_postiz_http.py::test_post_500_is_not_retried` | ✓ |
| H3 `list_scheduled` через retry-helper | `test_coverage_gaps.py::test_postiz_http_list_scheduled_parses_and_filters` | ✓ |
| read-only: **все** мутации → 403 (вкл. `test/schedule`) | `test_residual_closure.py::test_read_only_blocks_all_mutations` + 2 новых | ✓ |
| SQL-инъекция (очередь/правка) | `test_test_publish.py::test_sql_injection_in_queue_edit_has_no_effect` (новый) | ✓ |
| Миграции (fresh/v11/duplicate/idempotent) | прогон в жёстком прогоне (4/4) + CI-тесты схемы | ✓ |
| GUI failure-resilience (500 → не белый экран) | `scripts/gui_check_failures.sh` (PASS, 10/10 экранов) | ✓ |

**Новые тесты (16, `tests/test_test_publish.py`):** disabled→403, allowlist→403, границы задержки, дефолт +1 мин,
префикс, **боевая строка не создаётся**, `scheduled_for` в прошлом→400, >45 МБ для Telegram→400,
link-режим (ссылка из `release_url`, без медиа), link без ссылки→400, entity not found→404,
dry-run ничего не создаёт, prod-guard→403, cancel только тестовых, API-level (schedule+status+cancel+валидации),
read-only→403 для нового маршрута.

## C. Полный прогон

| Проверка | Результат |
|---|---|
| `pytest` | **255 passed** |
| `./scripts/check.sh` | ALL CHECKS PASSED |
| `ruff check src/ tests/` | All checks passed |
| `./scripts/gui_check.sh` (против **боевого** сервера, b814) | GUI-ПРОВЕРКА ПРОЙДЕНА (папки/поиск/JS-ошибок нет) |
| Ошибки циклов после деплоя | 0 (journalctl за 15 мин) |

## D. Живой E2E (боевой сервер, 21.09.2026)

1. **YouTube, media-режим** — short 270, +1 мин: пост `cmub43li4…` → **PUBLISHED**
   `https://www.youtube.com/watch?v=5JeLhbun98k`, заголовок `[orch-test] Одиночество в эпоху уведомлений`
   (проверено на странице видео), 10:39:14 UTC.
2. **Telegram, link-режим** — short 304 (YouTube уже опубликован), +1 мин: пост `cmub4eemy…` → **PUBLISHED**
   `https://t.me/tochkanablyudeniya/8`, текст начинается с `[orch-test]` и содержит ссылку на YouTube, 10:47:38 UTC.
3. **Негативные live-кейсы:** несуществующая сущность → 404; платформа вне allowlist → 400/403; задержка 999 → 400;
   dry-run → `dry_run:true`, без создания поста.
4. **Telegram media >45 МБ** (до фикса) → ERROR `413 Request Entity Too Large` от Bot API —
   воспроизведено и закрыто предохранителем + link-режимом (кейс задокументирован).
5. **Отмена:** все 3 тест-поста сняты `/test/cancel` → `{"ok":true}`; сообщение в канале удалено админ-ботом
   оркестратора (deleteMessage → ok).
6. **Боевая сетка не тронута:** `entity_platform_status` = **82 строки до и после** (39 ready / 39 scheduled /
   4 published — без изменений); счётчики `/status` те же; журнал: 3×test_scheduled, 3×test_cancelled, 1×test_dry_run.

## E. Найденный и исправленный дефект инфраструктуры (вне плана, D9)

После деплоя 8.2.0 меню-кнопка бота осталась на `/webapp/b/813/` → **404** (панель живёт по build-пути).
Причина: `cloudflared_url_sync.sh` искал URL туннеля в `journalctl`, а журнал уже ротирован («no url yet»),
и не срабатывал fallback. Исправлено: скрипт переписан (fallback URL из state-файла, build читается из кода,
**без legacy-пути** `/webapp/k/`, ключ в query), версия положена в репо `scripts/cloudflared_url_sync.sh`,
установлена на сервер. Проверено: `getChatMenuButton` (default и per-chat) → `/webapp/b/814/?key=…`, панель 200.

## F. Артефакты и остаточные замечания

- **Коммит:** `133286d` (master, запушен). **Файлы:** `src/orchestrator/test_publish.py`, правки
  `config.py`/`main.py`/`webapp_api.py`/`webapp/app.js`/`config.yaml`, `tests/test_test_publish.py`,
  `scripts/cloudflared_url_sync.sh`, `CHANGELOG.md`, доки.
- **YouTube-ролик теста** `[orch-test] Одиночество…` (watch?v=5JeLhbun98k) остался на тест-канале:
  удаление Postiz-поста не удаляет видео с платформы (нужен YouTube API/provider-revoke). Можно удалить
  вручную в YouTube Studio; на боевую сетку не влияет.
- `test_publish` включён для тестовых каналов (youtube/telegram). При переходе на боевые каналы — либо
  выключить `enabled`, либо вписать их `integration_id` в `prod_integration_ids`.
- Слот **18:00 МСК** (шорт 305 + Telegram-ссылка 18:15) не затронут — взведён и ждёт.
- Побайтовая проверка SSD по-прежнему на паузе (нужен подключённый SSD) — вне рамок этой задачи.
