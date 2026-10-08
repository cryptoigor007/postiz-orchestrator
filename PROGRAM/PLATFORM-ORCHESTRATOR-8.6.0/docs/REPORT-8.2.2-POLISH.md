# Отчёт 8.2.2 — Residual polish (XSS-хвосты, rate-limit uid, CHANGELOG/docs)

**Дата:** 2026-09-21 · **Версия:** 8.2.2 · **Сборка:** b816 · **Коммит:** (см. `git log -1`)
**Тесты:** 305 (было 304; +1) · **ruff:** 0 · `check.sh`: PASS · `gui_check.sh` (боевой): PASS
**База:** 8.2.1 (`66b2050`/`6df3702`); правки — только остаточный polish, без переписывания P0.

## Что закрыто (фикс ↔ файл)

| # | Пункт | Файл | Что сделано |
|---|-------|------|-------------|
| R1 | XSS-хвосты | `webapp/app.js` | 11 мест: `d.parent` (cover-навигация), `data-p` в browse/roots/parent, `it.title` (календарь), `data-video`, `value=` поиска папок, bulk-теги, `x.at` кадров, `title` pIcon, `day.count` → полный `esc()`. Частичные `.replace(/"/g)` заменены на `esc()`. Итог: **66 вызовов esc**, финальный grep «сырые `${…path/name/title/url/error…}` в HTML» — пусто |
| R2 | rate-limit uid | `src/orchestrator/webapp_api.py` | `_rate_limited(headers, auth)`: user id только из **HMAC-валидированного** initData (тот же `auth`, что вернула `_auth`); приоритет key → uid → первый XFF → local. Regex по сырому заголовку удалён |
| R3 | CHANGELOG hygiene | `CHANGELOG.md` | Ровно один `# Changelog` (проверено assert'ом), секция 8.2.2 сверху |
| R4 | Docs | `README.md`, `docs/HANDOFF.md` | 8.2.2 / b816 / 305 тестов; секретов нет (только имена env) |
| R5 | CSP + тест | `src/orchestrator/http_server.py`, `tests/test_p0_residual.py` | TODO переформулирован: nonce/hash в 8.3 при выносе inline-bootstrap; добавлен тест uid-bucket (разные подписи одного пользователя → один bucket; сырой initData bucket не создаёт) |

## Gate

| Проверка | Результат |
|---|---|
| `pytest tests/ -q` | **305 passed** |
| `ruff check src/ tests/ scripts/` | All checks passed |
| `./scripts/check.sh` | ALL CHECKS PASSED |
| `./scripts/gui_check.sh` (боевой, b816) | GUI-ПРОВЕРКА ПРОЙДЕНА (папки/поиск/JS-ошибки) |
| Деплой | 8.2.2, b816, сервис active, меню-кнопка `…/webapp/b/816/?key=…` |
| Панель | `/webapp/b/816/?key=…` → 200 |
| Боевые счётчики | 39 scheduled / 39 ready / 4 published (без изменений) |
| Ошибки циклов | 0 (journal за 5 мин) |

## Residual risks (честно)

1. **Два тестовых ролика на YouTube** (`watch?v=5JeLhbun98k`, `watch?v=6HW23NkJMrg`) — Postiz-delete не удаляет с платформы; снести вручную в YouTube Studio (ops-инструкция достаточна, helper через engine.delete не делал).
2. **CSP** — `'unsafe-inline'` остаётся до 8.3 (план: nonce/hash при выносе инлайн-скрипта). XSS-поверхность закрыта `esc()` в UI, но организационной гарантии (линтер «нет сырых вставок») нет — только регулярный grep-пасс (сейчас чистый).
3. **Авто-TTL тест-постов** (24ч) живьём пока не тикал — нет постов старше TTL; юнит зелёный.
4. **initData freshness** (>24ч → 401) — по замыслу, вживую не воспроизводили (нет старой сессии).
5. **YouTube-удаление тестового видео через engine** — не реализовано (опциональный пункт R5), не блокер.
6. P1.10 (429 Bot API) и метрики `test_*` — юнит-проверка, живой инцидент не форсировали.

## Как это проверено

- XSS: ручной grep-скан по всем `innerHTML`-шаблонам с именами данных (`path/parent/name/title/url/error/warning/...`) → 0 неэкранированных; `gui_check.sh` против боевого сервера — PASS.
- Rate-limit: юнит с двумя валидными HMAC-подписями одного uid → один bucket, лимит срабатывает на 3-м запросе; невалидный init → отдельный anon-bucket.
- Деплой и живой прод — командами `deploy.sh` + `gui_check.sh` + API `/status` (см. таблицу Gate).
