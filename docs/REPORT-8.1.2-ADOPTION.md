# Отчёт: приём и боевое развёртывание postiz-orchestrator-linux 8.1.2

Дата: 2026-09-21. Исполнитель: opencode (агент на Mac пользователя).
Входной артефакт: `postiz-orchestrator-linux-8.1.2 (1).tar.gz` (254 658 байт, 155 файлов).
Проверяемый контур: сервер pve (192.168.100.40), оркестратор `/opt/orchestrator`, Postiz VM 120.

---

## 1. Резюме

**8.1.2 принята, развёрнута и работает в проде.** По ходу приёма найдены и исправлены
**7 функциональных дефектов** (из них 5 — в инструментарии 8.1.2, 1 — в watcher, 1 — в url-sync),
а также 1 UI-пробел (статус `publishing`) и 1 дефект теста. Итоговое состояние:

| Метрика | Значение |
|---|---|
| Версия на сервере | `__version__ = "8.1.2"` |
| UI-сборка | `WEBAPP_BUILD = "813"` (было 812; +статус publishing) |
| Схема БД | `schema_version = 12` (миграция 8.1.2 применена) |
| Индекс | `idx_eps_postiz_id_unique` создан |
| Тесты | **234 passed** (в архиве 233; +1 на устойчивость watcher) |
| ruff | 0 ошибок (в архиве было 14) |
| GUI-проверка (jsdom) | локально и **против боевого сервера** — зелёные |
| Очередь | published 4 · scheduled 39 · ready 39 |
| Ошибки в цикле после фиксов | **0** |
| Откат | `/root/orchestrator_rollback_20260921_120525.tar.gz` (21 МБ) |

Проверка идентичности: MD5 `publisher.py`, `watcher.py`, `backup.py` на сервере **совпадают**
с репозиторием (master). Из 155 файлов архива **135 байт-в-байт**; 20 отличаются осознанно
(13 — наши фиксы/тесты, 7 — наши `config.yaml`/docs, которые нельзя было заменять:
в конфиге архива `integration_id` пустые).

---

## 2. Этап 0 — локальная проверка архива (в /tmp, прод не затрагивался)

1. Распаковка в `/tmp/grok812/postiz-orchestrator-linux`.
2. `ruff check src scripts tests` → **14 ошибок** (см. дефект D1).
3. `PYTHONPATH=src pytest tests/ -q` → **233 passed** ✓
4. `bash scripts/stage_run.sh` → **падал** (см. дефект D2).
5. `scripts/gui_check.sh` → **не работал** (см. дефекты D4–D5): все экраны пустые, затем
   падение по `TypeError` в check.mjs.

После фиксов: ruff 0 ошибок, 233 теста зелёные, стенд проходит, GUI-проверка — PASSED.

---

## 3. Найденные дефекты 8.1.2 и что исправлено

### D1. Линтер: 14 ошибок (CI 8.1.2 упал бы)
- `src/orchestrator/http_server.py`, `src/orchestrator/webapp_api.py`, `tests/test_backup_api.py`,
  `tests/test_closure_8_1.py`, `tests/test_residual_closure.py` — `I001` (порядок импортов).
- `src/orchestrator/media.py` — `F401` неиспользуемый `import time`;
  **`E402` — импорты стояли ПОСЛЕ кода** (функция `_cached_size` объявлена выше `import os`).
- Фикс: импорты подняты в начало файла, мёртвый `time` удалён, сортировка импортов выровнена
  (`ruff --fix`). После — `ruff check` = 0.

### D2. `backup.py` — падение всего цикла `--once` (из-за пути бэкапа)
- Симптом: `python -m orchestrator.main --once` (и их же `stage_run.sh`) падал:
  `PermissionError: '/private/backups'`.
- Причина: `bdir = Path(args.db).resolve().parent.parent / "backups"` — для БД вне штатной
  раскладки (`/tmp/orchestrator_stage.sqlite`) даёт `/backups`.
- Фикс: устойчивый выбор папки (проверка `os.access(W_OK)`), fallback на `<папка БД>/backups`,
  и если ничего недоступно — предупреждение и `return None` (без исключения).

### D3. `main.py` — бэкап ронял весь цикл
- Фикс: вызов `run_backup(...)` обёрнут в `try/except` с логом («не критично, продолжаем»).

### D4. `tests/gui/check.mjs` — ключ брался только из пути `/webapp/k/`
- Симптом: для нового URL `/webapp/b/<build>/` все предзагрузочные API-запросы уходили **без
  ключа** → `401` → пустые фикстуры → **все экраны «пусто/ошибка»**.
- Фикс: `const key = process.env.WEBAPP_ACCESS_KEY || (path-match /webapp/k/…)`.

### D5. `scripts/gui_check.sh` — три дефекта
1. Жёсткий `GUI_URL=…/webapp/b/811/` при `WEBAPP_BUILD=812` → **404** (гейтинг `bprefix`).
   Фикс: build читается из `src/orchestrator/webapp_api.py`; иначе `/webapp/`.
2. `export WEBAPP_ACCESS_KEY="${KEY:-$WEBAPP_ACCESS_KEY}"` падал при `set -u`, если ключа нет.
   Фикс: `"${KEY:-${WEBAPP_ACCESS_KEY:-}}"`.
3. Ключ не попадал **в URL самой страницы** → приложение показывало экран авторизации
   (`boot(): if (!initData && !dev && !state.key) → gate`) и ничего не рендерило.
   Фикс: ключ добавляется в `GUI_URL` (`?key=…`, учитывая `&`), заголовок остаётся.

### D6. `watcher.py` — скан падал на одной недоступной папке (и убивал весь цикл раннера)
- Инцидент в проде: `PermissionError: /mnt/video/ssd_backup/кальянная/vertical`
  (файлы скопированы с macOS с uid 501 / rwx------). Цикл раннера падал каждые несколько секунд:
  **412 трейсбеков за 8 минут (114/мин)**, очередь/ссылки не обрабатывались
  (`Cycle error (streak=N, backoff=…)`).
- Фикс: `_walk` обёрнут в `try/except OSError` (лог + пропуск), добавлен тест
  `test_watcher_survives_permission_denied_dir`. Плюс на сервере исправлены права
  (`chown orchestrator` + `755/644` на `/mnt/video/ssd_backup`).

### D7. `deploy/cloudflared_url_sync.sh` — меню-кнопка не обновлялась
- Симптом: `no url yet`, `WEBAPP_PUBLIC_URL` и файл состояния не менялись → меню-кнопка
  Telegram вела на старый (404) URL.
- Причина: базовый URL брался только из `journalctl -u cloudflared-webapp`, а журнал был
  очищен ранее (`SystemMaxUse=300M`, `journalctl --vacuum-size=300M`) → пусто.
- Фикс: если из журнала пусто — базовый URL восстанавливается из
  `/var/lib/cloudflared-webapp.url` (state-файл).

### D8 (мелкое, UI/тесты)
- Статус `publishing` (новый резерв при создании поста, R1') не был известен панели:
  добавлен i18n ru/en («публикуется»/«publishing») и включён в выборку очереди → `b813`.
- `tests/test_closure_8_1.py::test_webapp_build_id` сравнивал «магическое» `"812"` — при
  корректном bump сборки тест ломается. Заменено на проверку формата (только цифры, path-safe).

---

## 4. Этап 1 — приём в репозиторий

- Ветка `grok-8.1.2` → затем fast-forward в `master`.
- Заменено из архива: `src/ webapp/ scripts/ tests/ deploy/ docs/` + корневые
  `CHANGELOG.md, STAGE_ACCEPTANCE.md, CHECKLIST*.md, pytest.ini, ruff.toml, .github/, .githooks/,
  requirements.txt, .env.example, config.stage.yaml, AGENTS.md`.
- **Не заменялись** (осознанно): `config.yaml` (в архиве санитизирован: `integration_id: ""` —
  это сломало бы публикации; наш конфиг имеет реальные id и `postiz_create_per_hour: 60`),
  `config.yaml.bak`, `.env`, БД, `docs/SESSION_LOG.md` (дополнен), `README.md`, `.gitignore`.
- Диф ключей конфига «их vs наш» — **пустой**: код 8.1.2 совместим с нашим конфигом без правок.
- Коммиты (GitHub, ветка master):

| Коммит | Что |
|---|---|
| `5224de8` | adopt 8.1.2 + 5 фиксов инструментария (D1–D5), 233 теста |
| `71df444` | watcher hardening (D6) + url-sync fallback (D7) |
| `3823fb3` | журнал деплоя на сервер |
| `6e1ad83` | b813: статус `publishing` в UI и очереди (D8а) |
| `427e411` | тест build-id проверяет формат (D8б) |
| `94532a4`, `084f582` | журнал/версии в документации |

---

## 5. Этап 2 — боевой деплой (сервер)

1. **Бэкап отката**: `tar -czf /root/orchestrator_rollback_20260921_120525.tar.gz orchestrator`
   (без venv/data/logs/backups) — 21 060 043 байт.
2. Сверка конфигов: серверный `config.yaml` и наш — **идентичны** (перезаписи не произошло).
3. `./scripts/deploy.sh` (rsync кода; `.env`/`config.yaml`/БД не затрагиваются).
4. В `.env` добавлен `ORCH_HTTP_BIND=0.0.0.0` (нужен для LAN-проверок с Mac; дефолт 8.1.2 —
   `127.0.0.1`).
5. Рестарт, миграция БД: `schema_version 11 → 12`, создан `idx_eps_postiz_id_unique`.
6. **Инцидент D6 в проде (таймлайн)**:
   - 12:00–12:07 — цикл раннера падает: `PermissionError: /mnt/video/ssd_backup/кальянная/vertical`
     (маковские права после ночной догрузки файлов), `Cycle error (streak=1..6, backoff=1..64s)`,
     всего 412 трейсбеков;
   - 12:07 — исправлены права на сервере (`chown -R orchestrator`, `755`/`644`);
   - 12:08:05 — цикл восстановлен (`Watch: {...}`), далее — 0 ошибок;
   - в код добавлен hardening `_walk` (D6) + тест; задеплоено.
7. **Инцидент D7**: меню-кнопка не обновлялась (журнал пуст) — фикс + ручной прогон синка:
   URL панели обновлён на `https://<tunnel>/webapp/b/812/`, затем `b/813` (после UI-фикса).

---

## 6. Этап 3 — боевые проверки после деплоя

| Проверка | Результат |
|---|---|
| Панель (новый URL, без ключа в пути) | HTTP **200**, страница содержит наш UI |
| Меню-кнопка Telegram | обновлена (`/webapp/b/813/`), `WEBAPP_PUBLIC_URL` синхронизирован |
| GUI-проверка (jsdom) против **прод-сервера** | **ПРОЙДЕНА** (все экраны, фильтры, дни, мультивыбор, обложка ×4 источника, удаление, поиск папок, 0 JS-ошибок) |
| Reconcile с Postiz | `missing: 0, orphans: 0` |
| Публикация 12:00 (шорт 304) | YouTube: https://www.youtube.com/watch?v=3IFDDfJHoh4 |
| Telegram-ссылка шорта 304 | **опубликована** 12:16 → https://t.me/tochkanablyudeniya/7 |
| Следующий слот | 18:00 МСК — шорт 305 (YouTube) + ссылка 18:15 |
| Ошибки цикла после 12:09 | **0** |
| Сервисы/таймеры | orchestrator, cloudflared-webapp, vm-nat, infra-watchdog, net-watchdog — active |

---

## 7. Текущее состояние (снимок)

```
версия:            8.1.2           схема БД: 12 (+ idx_eps_postiz_id_unique)
UI-сборка:         813             тесты:    234 passed / ruff 0
очередь:           published 4 · scheduled 39 · ready 39
панель:            https://<cloudflared-quick-tunnel>/webapp/b/813/
откат:             /root/orchestrator_rollback_20260921_120525.tar.gz (21 МБ)
репозиторий:       GitHub master @ 084f582 (8.1.2 + 7 фиксов)
```

---

## 8. Рекомендации в апстрим 8.1.x (чтобы 8.1.3 не повторял)

1. **CI**: добавить в пайплайн `ruff check src scripts tests` (14 текущих ошибок) — иначе
   «зелёный CI» не соответствует коду (E402 в `media.py`, I001 в 5 файлах, F401).
2. **`backup.py`**: не выводить путь бэкапа как `db.parent.parent / "backups"` без проверки;
   при недоступности — не бросать исключение (иначе падает `--once` и `stage_run.sh`).
3. **`main.py`**: вызов `run_backup` обернуть в `try/except` (бэкап не должен ронять цикл).
4. **`tests/gui/check.mjs`**: брать ключ из `WEBAPP_ACCESS_KEY` (иначе новый URL `/webapp/b/`
   без пути-ключа полностью ломает GUI-проверку: все API → 401).
5. **`scripts/gui_check.sh`**: build-id читать из исходников (жёсткий `811` при `812` → 404);
   учесть `set -u` (`${KEY:-${WEBAPP_ACCESS_KEY:-}}`); добавлять ключ в URL страницы
   (иначе приложение показывает экран авторизации — `boot()` требует `initKey|initData|dev`).
6. **`watcher._walk`**: обернуть обход в `try/except OSError` — одна недоступная папка не должна
   ронять весь цикл раннера (в проде это дало 412 трейсбеков и остановку планирования).
7. **`cloudflared_url_sync.sh`**: fallback базового URL из state-файла, если журнал cloudflared
   очищен (`SystemMaxUse`) — иначе меню-кнопка «замерзает» на старом URL.
8. **Статус `publishing`** (R1'): добавить `st_publishing` в i18n панели и включить статус в
   выборку очереди (`WHERE eps.status IN (… 'publishing')`), иначе строка мигает/выпадает.
9. **Тесты-константы**: `test_webapp_build_id` не должен проверять конкретное значение
   (`"812"`) — только формат (цифры/path-safe), иначе любой bump сборки ломает тесты.
10. **Процедура копирования медиа с macOS**: после rsync-копий на Linux-сервер обязательно
    `chown -R orchestrator` + `chmod 755/644` (macOS-права uid 501/700 ломают скан).

---

## 9. Как воспроизвести проверки

```bash
# локально
cd /path/to/postiz-orchestrator-linux
ruff check src scripts tests
PYTHONPATH=src pytest tests/ -q            # 234 passed
bash scripts/stage_run.sh                  # стенд (temp БД, dry-run)

# GUI (нужен запущенный инстанс; для прода — из окружения)
GUI_URL="https://<tunnel>/webapp/b/813/?view=queue" \
WEBAPP_ACCESS_KEY="<ключ>" bash scripts/gui_check.sh

# сервер
ssh root@192.168.100.40 'cd /opt/orchestrator && \
  grep -m1 __version__ src/orchestrator/__init__.py && \
  sqlite3 data/data.sqlite "SELECT value FROM system_state WHERE key=\"schema_version\";"'
```
