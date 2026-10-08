# Отчёт 8.2.3 — Закрытие residual-списка 8.2.2 (CSP, тест-ролики, живые проверки)

**Дата:** 2026-09-21 · **Версия:** 8.2.3 · **Сборка:** b817 · **Коммит:** (см. `git log -1`)
**Тесты:** 308 (было 305; +3) · **ruff:** 0 · `check.sh`: PASS · `gui_check.sh` (боевой): PASS

## Пункты residual-списка 8.2.2 → статус

| # | Пункт | Статус | Как проверено |
|---|-------|--------|----------------|
| 1 | Два тест-ролика на YouTube | ✅ **удалены** | `scripts/yt_cleanup_test_videos.py` (broker → OAuth-refresh → direct engine): `5JeLhbun98k`, `6HW23NkJMrg` удалены; страницы видео пусты; на канале остались **2 боевых** видео («Куда пропала вера в завтрашний день?», «ИИ не главный твой страх») |
| 2 | CSP `'unsafe-inline'` для скриптов | ✅ **закрыт** | per-request **nonce** на инлайн `style`/`script` (`_compose_index` → `http_server._send`); `script-src 'self' https://telegram.org 'nonce-…'` **без** `unsafe-inline`; добавлены `object-src 'none'`, `base-uri 'none'`. `style-src` оставлен с `unsafe-inline` осознанно (style-атрибуты UI, косметика — зафиксировано в коде) |
| 3 | TTL авто-очистки живьём не тикал | ✅ **проверен live** | Создан тест-пост (telegram link, +120 мин) → `created_at` состарен на 48ч → рестарт сервиса → первый цикл runner: `Test auto-cleanup: removed 1 expired test post(s)`, запись `test_auto_cancelled`, пост снят **до** публикации |
| 4 | initData>24ч → 401 | ✅ **проверен live** | На боевом сервере, реальный bot-token: свежий initData → **200**; initData с `auth_date` 3 суток → **401** |
| 5 | Метрики `test_*` и 429 Bot API | ✅ частично live | Метрика `test_cancelled: 1` видна в `/webapp/api/metrics` после TTL-очистки (flush — к концу следующего цикла watcher). 429-путь транспорта — **юнит-тест** (429 → пауза Retry-After 2с → повтор ok); в живом инциденте не форсировался |

## Дополнительно найдено/исправлено в этом проходе

- **Хардкод сборки в новых CSP-тестах** (`/webapp/b/816/`): тесты упали при bump 816→817 — исправлено на `WEBAPP_BUILD` из кода (тот же класс ошибки, что b811→813 ранее).
- `scripts/yt_cleanup_test_videos.py`: dry-run по умолчанию, `--yes` для удаления, фильтр строго по `test_publish.title_prefix`.
- Проверено (не баг): `direct_youtube.list_uploads` корректно отдаёт `external_id` (None в моём разовом скрипте был из-за неверного ключа `id`, а не в коде).

## Gate

| Проверка | Результат |
|---|---|
| `pytest` | **308 passed** |
| `ruff` | 0 |
| `check.sh` | ALL CHECKS PASSED |
| `gui_check.sh` (боевой, b817) | PASS — **панель работает под новым CSP** (nonce корректен, JS-ошибок нет) |
| CSP live | заголовок `script-src … 'nonce-X'`, тело содержит `nonce="X"`, совпадают; `unsafe-inline` в script-src отсутствует |
| Деплой | 8.2.3, b817, сервис active, меню-кнопка 817 |
| Боевые счётчики | 39/39/4 без изменений (проверено после рестарта) |

## Residual (что осталось честно)

1. **`style-src 'unsafe-inline'`** — сохраняется до рефакторинга style-атрибутов UI в классы (риск косметический; script-вектор закрыт nonce).
2. **429 Bot API в проде** — не форсировался (юнит-тест зелёный, live не наблюдался).
3. **Метрики `test_rejected`/`test_scheduled`** — `test_cancelled` подтверждён live; остальные проверены юнит-тестом.
4. TTL-очистка: подтверждена через реальный цикл runner при рестарте; в штатном режиме цикл идёт раз в час.
